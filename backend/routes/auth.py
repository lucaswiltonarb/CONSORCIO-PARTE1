# Autenticação JWT multi-usuário - PROMPT MESTRE
from fastapi import APIRouter, HTTPException, Request, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import os
import bcrypt
import jwt
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

JWT_ALGORITHM = "HS256"
db: AsyncIOMotorDatabase = None


def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            token = header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Não autenticado")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sessão expirada")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return user


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = "attendant"


class PasswordChange(BaseModel):
    password: str


async def check_lockout(identifier: str):
    doc = await db.login_attempts.find_one({"identifier": identifier})
    if doc and doc.get("count", 0) >= 5:
        locked_until = doc.get("locked_until")
        if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail="Muitas tentativas. Tente em 15 minutos.")


async def register_failure(identifier: str):
    doc = await db.login_attempts.find_one({"identifier": identifier})
    count = (doc.get("count", 0) if doc else 0) + 1
    await db.login_attempts.update_one(
        {"identifier": identifier},
        {"$set": {
            "count": count,
            "locked_until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
        }},
        upsert=True,
    )


@router.post("/login")
async def login(data: LoginInput, request: Request):
    email = data.email.lower().strip()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"
    await check_lockout(identifier)

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(data.password, user.get("password_hash", "")):
        await register_failure(identifier)
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")

    if user.get("active") is False:
        raise HTTPException(status_code=403, detail="Usuário desativado")

    await db.login_attempts.delete_one({"identifier": identifier})
    token = create_access_token(user["id"], user["email"], user.get("role", "attendant"))
    return {
        "token": token,
        "user": {"id": user["id"], "email": user["email"], "name": user.get("name"), "role": user.get("role")},
    }


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@router.get("/users")
async def list_users(admin: dict = Depends(require_admin)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(200)
    return {"users": users}


@router.post("/users")
async def create_user(data: UserCreate, admin: dict = Depends(require_admin)):
    email = data.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")
    doc = {
        "id": str(uuid4()),
        "email": email,
        "name": data.name,
        "role": data.role if data.role in ("admin", "attendant") else "attendant",
        "password_hash": hash_password(data.password),
        "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(doc)
    doc.pop("password_hash", None)
    doc.pop("_id", None)
    return dict(doc)


@router.patch("/users/{user_id}/password")
async def change_password(user_id: str, data: PasswordChange, admin: dict = Depends(require_admin)):
    result = await db.users.update_one(
        {"id": user_id}, {"$set": {"password_hash": hash_password(data.password)}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return {"status": "senha_atualizada"}


@router.patch("/users/{user_id}/toggle")
async def toggle_user(user_id: str, admin: dict = Depends(require_admin)):
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    new_state = not user.get("active", True)
    await db.users.update_one({"id": user_id}, {"$set": {"active": new_state}})
    return {"status": "atualizado", "active": new_state}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_admin)):
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if user["email"] == os.environ.get("ADMIN_EMAIL", "").lower():
        raise HTTPException(status_code=400, detail="Não é possível remover o administrador principal")
    await db.users.delete_one({"id": user_id})
    return {"status": "removido"}


async def seed_admin(database: AsyncIOMotorDatabase):
    """Cria/atualiza o administrador principal a partir do .env"""
    email = os.environ.get("ADMIN_EMAIL", "").lower().strip()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not email or not password:
        return
    existing = await database.users.find_one({"email": email})
    if not existing:
        await database.users.insert_one({
            "id": str(uuid4()),
            "email": email,
            "name": "Administrador",
            "role": "admin",
            "password_hash": hash_password(password),
            "active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(f"Admin criado: {email}")
    elif not verify_password(password, existing.get("password_hash", "")):
        await database.users.update_one(
            {"email": email}, {"$set": {"password_hash": hash_password(password), "role": "admin", "active": True}}
        )

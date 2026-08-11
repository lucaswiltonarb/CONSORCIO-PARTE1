# Rotas de Configurações
from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from models import Settings, SettingsUpdate
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])

db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database

@router.get("")
async def get_settings():
    """Busca configurações atuais"""
    settings = await db.settings.find_one({"id": "main_settings"}, {"_id": 0})
    
    if not settings:
        # Cria configurações padrão
        default = Settings()
        await db.settings.insert_one(default.model_dump())
        return default.model_dump()
    
    return settings

@router.patch("")
async def update_settings(update: SettingsUpdate):
    """Atualiza configurações"""
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.settings.update_one(
        {"id": "main_settings"},
        {"$set": update_data},
        upsert=True
    )
    
    return {"status": "updated", "modified": result.modified_count}

@router.get("/qualification-rules")
async def get_qualification_rules():
    """Busca regras de qualificação"""
    settings = await db.settings.find_one({"id": "main_settings"}, {"_id": 0})
    if not settings:
        return Settings().qualification_rules
    return settings.get("qualification_rules", {})

@router.put("/qualification-rules")
async def update_qualification_rules(rules: dict):
    """Atualiza regras de qualificação"""
    await db.settings.update_one(
        {"id": "main_settings"},
        {"$set": {
            "qualification_rules": rules,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    return {"status": "updated"}

@router.put("/system-prompt")
async def update_system_prompt(prompt: str):
    """Atualiza prompt do sistema"""
    await db.settings.update_one(
        {"id": "main_settings"},
        {"$set": {
            "system_prompt": prompt,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    return {"status": "updated"}

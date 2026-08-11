# Módulo de Treinamento - Importação de conversas históricas
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional
from routes.auth import get_current_user
from services.claude_service import generate_playbook
import re
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/training", tags=["training"])

db: AsyncIOMotorDatabase = None


def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database


LINHA_WA = re.compile(r"^\[?(\d{1,2}/\d{1,2}/\d{2,4})[,\s]+(\d{1,2}:\d{2})(?::\d{2})?\]?\s*[-–]?\s*([^:]{1,40}):\s*(.*)$")


def parse_whatsapp_export(conteudo: str) -> list:
    """Converte export .txt do WhatsApp em lista de mensagens"""
    mensagens = []
    for linha in conteudo.splitlines():
        m = LINHA_WA.match(linha.strip())
        if m:
            texto = m.group(4).strip()
            if not texto or "mensagem apagada" in texto.lower() or "<Mídia" in texto or "<Media" in texto:
                continue
            mensagens.append({"data": m.group(1), "hora": m.group(2), "autor": m.group(3).strip(), "texto": texto})
        elif mensagens and linha.strip():
            mensagens[-1]["texto"] += " " + linha.strip()
    return mensagens


@router.post("/import")
async def import_conversations(
    file: UploadFile = File(...),
    especialista: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
):
    """Importa export de conversas do WhatsApp (.txt) e gera playbook com IA"""
    conteudo = (await file.read()).decode("utf-8", errors="ignore")
    mensagens = parse_whatsapp_export(conteudo)

    if not mensagens:
        # Fallback: usa o texto puro caso não siga o formato do WhatsApp
        if len(conteudo.strip()) < 50:
            raise HTTPException(status_code=400, detail="Arquivo vazio ou formato não reconhecido")
        texto_conversas = conteudo
    else:
        texto_conversas = "\n".join([f"{m['autor']}: {m['texto']}" for m in mensagens])

    playbook = await generate_playbook(texto_conversas)

    doc = {
        "id": str(uuid4()),
        "arquivo": file.filename,
        "especialista": especialista or "não informado",
        "total_mensagens": len(mensagens),
        "playbook": playbook,
        "amostra": texto_conversas[:3000],
        "ativo": True,
        "importado_por": user.get("email"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.playbooks.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/playbooks")
async def list_playbooks(user: dict = Depends(get_current_user)):
    items = await db.playbooks.find({}, {"_id": 0, "amostra": 0}).sort("created_at", -1).to_list(100)
    return {"playbooks": items}


@router.get("/playbooks/{playbook_id}")
async def get_playbook(playbook_id: str, user: dict = Depends(get_current_user)):
    item = await db.playbooks.find_one({"id": playbook_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Playbook não encontrado")
    return item


@router.patch("/playbooks/{playbook_id}/toggle")
async def toggle_playbook(playbook_id: str, user: dict = Depends(get_current_user)):
    item = await db.playbooks.find_one({"id": playbook_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Playbook não encontrado")
    novo = not item.get("ativo", True)
    await db.playbooks.update_one({"id": playbook_id}, {"$set": {"ativo": novo}})
    return {"status": "atualizado", "ativo": novo}


@router.delete("/playbooks/{playbook_id}")
async def delete_playbook(playbook_id: str, user: dict = Depends(get_current_user)):
    await db.playbooks.delete_one({"id": playbook_id})
    return {"status": "removido"}


async def get_active_playbook_context(database: AsyncIOMotorDatabase) -> str:
    """Contexto consolidado dos playbooks ativos para o agente"""
    items = await database.playbooks.find({"ativo": True}, {"_id": 0, "playbook": 1}).to_list(5)
    return "\n\n---\n\n".join([i.get("playbook", "") for i in items if i.get("playbook")])

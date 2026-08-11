# Controle de documentação dos leads
from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from datetime import datetime, timezone
from routes.auth import get_current_user
from models import Event, FunnelStage
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

db: AsyncIOMotorDatabase = None

DOCUMENTOS_PADRAO = [
    "RG ou CNH",
    "CPF",
    "Comprovante de residência",
    "Comprovante de renda",
    "Selfie com documento",
    "Dados bancários",
]


def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database


class DocInput(BaseModel):
    documento: str


@router.get("/checklist")
async def checklist(user: dict = Depends(get_current_user)):
    return {"documentos": DOCUMENTOS_PADRAO}


@router.get("/{lead_id}")
async def lead_documents(lead_id: str, user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    solicitados = lead.get("documents_requested", [])
    recebidos = lead.get("documents_received", [])
    pendentes = [d for d in solicitados if d not in recebidos]
    total = len(solicitados) or 1
    return {
        "solicitados": solicitados,
        "recebidos": recebidos,
        "pendentes": pendentes,
        "progresso": round(len(recebidos) / total * 100),
        "completo": len(solicitados) > 0 and not pendentes,
    }


@router.post("/{lead_id}/request")
async def request_document(lead_id: str, data: DocInput, user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    await db.leads.update_one(
        {"id": lead_id},
        {
            "$addToSet": {"documents_requested": data.documento},
            "$set": {"stage": FunnelStage.DOCUMENTATION.value, "updated_at": datetime.now(timezone.utc).isoformat()},
        },
    )
    await db.events.insert_one(Event(
        lead_id=lead_id, event_type="documento_solicitado", metadata={"documento": data.documento, "por": user.get("email")}
    ).model_dump())
    return {"status": "solicitado", "documento": data.documento}


@router.post("/{lead_id}/receive")
async def receive_document(lead_id: str, data: DocInput, user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    await db.leads.update_one(
        {"id": lead_id},
        {
            "$addToSet": {"documents_received": data.documento, "documents_requested": data.documento},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
        },
    )
    await db.events.insert_one(Event(
        lead_id=lead_id, event_type="documento_recebido", metadata={"documento": data.documento, "por": user.get("email")}
    ).model_dump())
    return {"status": "recebido", "documento": data.documento}


@router.delete("/{lead_id}")
async def remove_document(lead_id: str, documento: str, user: dict = Depends(get_current_user)):
    await db.leads.update_one(
        {"id": lead_id},
        {"$pull": {"documents_requested": documento, "documents_received": documento}},
    )
    return {"status": "removido"}

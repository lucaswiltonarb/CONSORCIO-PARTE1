# Rotas de Chat - Intervenção Humana
from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from models import Message, MessageRole
from services.evolution_service import send_whatsapp_message
from routes.auth import get_current_user
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

db: AsyncIOMotorDatabase = None


def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database


class SendInput(BaseModel):
    lead_id: str
    content: str


@router.post("/send")
async def send_human_message(data: SendInput, user: dict = Depends(get_current_user)):
    """Envia mensagem como atendente humano"""
    lead = await db.leads.find_one({"id": data.lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    settings = await db.settings.find_one({"id": "main_settings"}, {"_id": 0})
    if not settings or not settings.get('evolution_api_url'):
        raise HTTPException(status_code=400, detail="Evolution API não configurada")

    msg = Message(lead_id=data.lead_id, role=MessageRole.HUMAN, content=data.content)
    doc = msg.model_dump()
    doc["atendente"] = user.get("email")
    await db.messages.insert_one(doc)

    # Ao responder manualmente, o atendente assume a conversa
    await db.leads.update_one(
        {"id": data.lead_id},
        {"$set": {
            "human_takeover": True,
            "assigned_to": user.get("email"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )

    success = await send_whatsapp_message(
        settings['evolution_api_url'],
        settings['evolution_api_key'],
        settings.get('evolution_instance', 'default'),
        lead['phone'],
        data.content
    )

    if not success:
        raise HTTPException(status_code=500, detail="Falha ao enviar mensagem no WhatsApp")

    return {"status": "sent", "message_id": msg.id}


@router.get("/active")
async def get_active_chats(user: dict = Depends(get_current_user)):
    """Lista conversas ativas"""
    pipeline = [
        {"$match": {"stage": {"$nin": ["lost"]}}},
        {"$lookup": {
            "from": "messages",
            "localField": "id",
            "foreignField": "lead_id",
            "as": "messages"
        }},
        {"$addFields": {
            "last_message": {"$arrayElemAt": [{"$slice": ["$messages", -1]}, 0]},
            "total_messages": {"$size": "$messages"}
        }},
        {"$project": {
            "_id": 0, "id": 1, "phone": 1, "name": 1, "stage": 1, "score": 1,
            "temperature": 1, "human_takeover": 1, "assigned_to": 1,
            "last_message": 1, "total_messages": 1, "updated_at": 1
        }},
        {"$sort": {"updated_at": -1}},
        {"$limit": 60}
    ]
    chats = await db.leads.aggregate(pipeline).to_list(60)
    return {"chats": chats}

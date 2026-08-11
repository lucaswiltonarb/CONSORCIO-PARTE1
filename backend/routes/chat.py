# Rotas de Chat - Intervenção Humana
from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from models import Message, MessageRole
from services.evolution_service import send_whatsapp_message
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database

@router.post("/send")
async def send_human_message(lead_id: str, content: str):
    """Envia mensagem como atendente humano"""
    # Busca lead
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    
    # Busca configurações
    settings = await db.settings.find_one({"id": "main_settings"}, {"_id": 0})
    if not settings or not settings.get('evolution_api_url'):
        raise HTTPException(status_code=400, detail="Evolution API não configurada")
    
    # Salva mensagem
    msg = Message(lead_id=lead_id, role=MessageRole.HUMAN, content=content)
    await db.messages.insert_one(msg.model_dump())
    
    # Envia via WhatsApp
    success = await send_whatsapp_message(
        settings['evolution_api_url'],
        settings['evolution_api_key'],
        settings.get('evolution_instance', 'default'),
        lead['phone'],
        content
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Falha ao enviar mensagem")
    
    return {"status": "sent", "message_id": msg.id}

@router.get("/active")
async def get_active_chats():
    """Lista conversas ativas (com mensagens recentes)"""
    # Busca leads com human_takeover ou mensagens recentes
    pipeline = [
        {"$match": {"stage": {"$nin": ["confirmed", "lost"]}}},
        {"$lookup": {
            "from": "messages",
            "localField": "id",
            "foreignField": "lead_id",
            "as": "messages"
        }},
        {"$addFields": {
            "last_message": {"$arrayElemAt": [{"$slice": ["$messages", -1]}, 0]},
            "unread_count": {
                "$size": {
                    "$filter": {
                        "input": "$messages",
                        "cond": {"$eq": ["$$this.role", "lead"]}
                    }
                }
            }
        }},
        {"$project": {
            "_id": 0,
            "id": 1,
            "phone": 1,
            "name": 1,
            "stage": 1,
            "temperature": 1,
            "human_takeover": 1,
            "last_message": 1,
            "updated_at": 1
        }},
        {"$sort": {"updated_at": -1}},
        {"$limit": 50}
    ]
    
    chats = await db.leads.aggregate(pipeline).to_list(50)
    return {"chats": chats}

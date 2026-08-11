# Rotas de Leads e Funil CRM
from fastapi import APIRouter, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from models import Lead, LeadCreate, FunnelStage, Message, MessageRole, Event
from services.meta_capi_service import send_event, EVENT_MAPPING
from typing import Optional, List
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/leads", tags=["leads"])

db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database

@router.get("")
async def list_leads(
    stage: Optional[str] = None,
    temperature: Optional[str] = None,
    human_takeover: Optional[bool] = None,
    limit: int = Query(default=50, le=200),
    skip: int = 0
):
    """Lista leads com filtros"""
    query = {}
    if stage:
        query["stage"] = stage
    if temperature:
        query["temperature"] = temperature
    if human_takeover is not None:
        query["human_takeover"] = human_takeover
    
    leads = await db.leads.find(query, {"_id": 0}).sort("updated_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.leads.count_documents(query)
    
    return {"leads": leads, "total": total}

@router.get("/{lead_id}")
async def get_lead(lead_id: str):
    """Busca lead por ID"""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    return lead

@router.get("/{lead_id}/messages")
async def get_lead_messages(lead_id: str, limit: int = 100):
    """Busca mensagens de um lead"""
    messages = await db.messages.find(
        {"lead_id": lead_id},
        {"_id": 0}
    ).sort("timestamp", 1).to_list(limit)
    
    return {"messages": messages}

@router.patch("/{lead_id}/stage")
async def update_lead_stage(lead_id: str, stage: FunnelStage):
    """Atualiza estágio do lead no funil"""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    
    await db.leads.update_one(
        {"id": lead_id},
        {"$set": {"stage": stage.value, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Registra evento
    event = Event(lead_id=lead_id, event_type=f"stage_changed_to_{stage.value}")
    await db.events.insert_one(event.model_dump())
    
    # Envia para Meta se configurado
    settings = await db.settings.find_one({"id": "main_settings"}, {"_id": 0})
    if settings and settings.get('meta_pixel_id'):
        event_name = EVENT_MAPPING.get(f"{stage.value}_started")
        if event_name:
            await send_event(
                settings['meta_pixel_id'],
                settings['meta_capi_token'],
                event_name,
                lead['phone']
            )
    
    return {"status": "updated", "stage": stage.value}

@router.post("/{lead_id}/takeover")
async def human_takeover(lead_id: str, assigned_to: Optional[str] = None):
    """Ativa intervenção humana para o lead"""
    result = await db.leads.update_one(
        {"id": lead_id},
        {"$set": {
            "human_takeover": True,
            "assigned_to": assigned_to,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    
    return {"status": "takeover_activated"}

@router.post("/{lead_id}/release")
async def release_to_agent(lead_id: str):
    """Devolve lead para o agente IA"""
    result = await db.leads.update_one(
        {"id": lead_id},
        {"$set": {
            "human_takeover": False,
            "assigned_to": None,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    
    return {"status": "released_to_agent"}

@router.post("/{lead_id}/confirm-sale")
async def confirm_sale(lead_id: str):
    """CONFIRMAÇÃO MANUAL de venda - APENAS HUMANOS"""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    
    await db.leads.update_one(
        {"id": lead_id},
        {"$set": {
            "stage": FunnelStage.CONFIRMED.value,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Registra evento de venda
    event = Event(
        lead_id=lead_id,
        event_type="sale_confirmed",
        metadata={"confirmed_at": datetime.now(timezone.utc).isoformat()}
    )
    await db.events.insert_one(event.model_dump())
    
    # Envia Purchase para Meta
    settings = await db.settings.find_one({"id": "main_settings"}, {"_id": 0})
    if settings and settings.get('meta_pixel_id'):
        await send_event(
            settings['meta_pixel_id'],
            settings['meta_capi_token'],
            "Purchase",
            lead['phone'],
            {"currency": "BRL", "value": 0}  # Valor pode ser configurado
        )
    
    logger.info(f"Venda confirmada manualmente: {lead_id}")
    return {"status": "sale_confirmed", "lead_id": lead_id}

@router.post("/{lead_id}/mark-lost")
async def mark_as_lost(lead_id: str, reason: Optional[str] = None):
    """Marca lead como perdido"""
    result = await db.leads.update_one(
        {"id": lead_id},
        {"$set": {
            "stage": FunnelStage.LOST.value,
            "meta_data.lost_reason": reason,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    
    return {"status": "marked_as_lost"}

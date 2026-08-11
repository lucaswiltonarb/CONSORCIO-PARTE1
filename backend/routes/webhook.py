# Rotas Webhook - Evolution API
from fastapi import APIRouter, Request, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorDatabase
from models import Lead, Message, MessageRole, FunnelStage, Event
from services.evolution_service import extract_message_from_webhook, send_whatsapp_message
from services.claude_service import generate_response, analyze_qualification
from services.meta_capi_service import send_event, EVENT_MAPPING
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])

# DB será injetado no startup
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database

async def process_incoming_message(phone: str, text: str, name: str):
    """Processa mensagem recebida em background"""
    try:
        # Busca ou cria lead
        lead_doc = await db.leads.find_one({"phone": phone}, {"_id": 0})
        
        if not lead_doc:
            lead = Lead(phone=phone, name=name or None)
            lead_doc = lead.model_dump()
            await db.leads.insert_one(lead_doc)
            logger.info(f"Novo lead criado: {phone}")
        else:
            # Atualiza nome se não tinha
            if name and not lead_doc.get('name'):
                await db.leads.update_one(
                    {"phone": phone},
                    {"$set": {"name": name, "updated_at": datetime.now(timezone.utc).isoformat()}}
                )
                lead_doc['name'] = name
        
        # Se humano assumiu, não responde automaticamente
        if lead_doc.get('human_takeover'):
            logger.info(f"Lead {phone} em atendimento humano")
            # Apenas salva mensagem
            msg = Message(lead_id=lead_doc['id'], role=MessageRole.LEAD, content=text)
            await db.messages.insert_one(msg.model_dump())
            return
        
        # Salva mensagem do lead
        msg = Message(lead_id=lead_doc['id'], role=MessageRole.LEAD, content=text)
        await db.messages.insert_one(msg.model_dump())
        
        # Busca configurações
        settings = await db.settings.find_one({"id": "main_settings"}, {"_id": 0})
        if not settings:
            logger.warning("Configurações não encontradas")
            return
        
        # Verifica se Evolution está configurado
        if not settings.get('evolution_api_url') or not settings.get('evolution_api_key'):
            logger.warning("Evolution API não configurada")
            return
        
        # Analisa qualificação
        qual_result = analyze_qualification(
            text,
            lead_doc.get('criteria_met', {}),
            settings.get('qualification_rules', {})
        )
        
        # Atualiza lead com nova qualificação
        new_score = lead_doc.get('score', 0) + qual_result['score_delta']
        new_criteria = qual_result['criteria_met']
        
        # Determina temperatura
        temperature = 'cold'
        if new_score >= 30:
            temperature = 'warm'
        if new_score >= 60:
            temperature = 'hot'
        
        # Atualiza estágio se qualificou
        new_stage = lead_doc.get('stage', 'new')
        min_score = settings.get('qualification_rules', {}).get('min_score_qualified', 50)
        
        if new_score >= min_score and new_stage == 'new':
            new_stage = 'qualified'
            # Envia evento Meta
            if settings.get('meta_pixel_id') and settings.get('meta_capi_token'):
                await send_event(
                    settings['meta_pixel_id'],
                    settings['meta_capi_token'],
                    EVENT_MAPPING.get('lead_qualified', 'Lead'),
                    phone
                )
        
        await db.leads.update_one(
            {"phone": phone},
            {"$set": {
                "score": new_score,
                "criteria_met": new_criteria,
                "temperature": temperature,
                "stage": new_stage,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Atualiza lead_doc para contexto
        lead_doc['score'] = new_score
        lead_doc['criteria_met'] = new_criteria
        lead_doc['temperature'] = temperature
        lead_doc['stage'] = new_stage
        
        # Busca histórico de mensagens
        messages = await db.messages.find(
            {"lead_id": lead_doc['id']},
            {"_id": 0}
        ).sort("timestamp", 1).to_list(50)
        
        # Gera resposta com IA
        response_text = await generate_response(
            [{'role': m['role'], 'content': m['content']} for m in messages],
            settings.get('system_prompt', ''),
            lead_doc
        )
        
        # Salva resposta do agente
        agent_msg = Message(
            lead_id=lead_doc['id'],
            role=MessageRole.AGENT,
            content=response_text
        )
        await db.messages.insert_one(agent_msg.model_dump())
        
        # Envia via WhatsApp
        await send_whatsapp_message(
            settings['evolution_api_url'],
            settings['evolution_api_key'],
            settings.get('evolution_instance', 'default'),
            phone,
            response_text
        )
        
    except Exception as e:
        logger.error(f"Erro processando mensagem: {e}")

@router.post("/evolution")
async def evolution_webhook(request: Request, background_tasks: BackgroundTasks):
    """Recebe webhooks da Evolution API"""
    try:
        payload = await request.json()
        logger.info(f"Webhook recebido: {payload.get('event', 'unknown')}")
        
        # Filtra apenas mensagens recebidas
        event = payload.get('event', '')
        if event not in ['messages.upsert', 'message', 'messages']:
            return {"status": "ignored", "event": event}
        
        # Extrai dados da mensagem
        msg_data = extract_message_from_webhook(payload)
        
        if not msg_data:
            return {"status": "no_message"}
        
        # Processa em background para resposta rápida
        background_tasks.add_task(
            process_incoming_message,
            msg_data['phone'],
            msg_data['text'],
            msg_data['name']
        )
        
        return {"status": "processing"}
        
    except Exception as e:
        logger.error(f"Erro webhook: {e}")
        return {"status": "error", "detail": str(e)}

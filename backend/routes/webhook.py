# Rotas Webhook - Evolution API
from fastapi import APIRouter, Request, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorDatabase
from models import Lead, Message, MessageRole, Event
from services.evolution_service import extract_message_from_webhook, send_whatsapp_message
from services.claude_service import (
    generate_response,
    analyze_qualification_ai,
    detect_human_request,
)
from services.meta_capi_service import send_event, EVENT_MAPPING
from routes.training import get_active_playbook_context
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])

db: AsyncIOMotorDatabase = None


def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database


async def process_incoming_message(phone: str, text: str, name: str):
    """Processa mensagem recebida em background"""
    try:
        lead_doc = await db.leads.find_one({"phone": phone}, {"_id": 0})

        if not lead_doc:
            lead = Lead(phone=phone, name=name or None)
            lead_doc = lead.model_dump()
            await db.leads.insert_one(dict(lead_doc))
            logger.info(f"Novo lead criado: {phone}")
        elif name and not lead_doc.get('name'):
            await db.leads.update_one(
                {"phone": phone},
                {"$set": {"name": name, "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            lead_doc['name'] = name

        # Salva mensagem do lead
        msg = Message(lead_id=lead_doc['id'], role=MessageRole.LEAD, content=text)
        await db.messages.insert_one(msg.model_dump())

        # Atendimento humano ativo: IA não responde
        if lead_doc.get('human_takeover'):
            logger.info(f"Lead {phone} em atendimento humano - IA silenciada")
            return

        settings = await db.settings.find_one({"id": "main_settings"}, {"_id": 0})
        if not settings:
            logger.warning("Configurações não encontradas")
            return

        if not settings.get('evolution_api_url') or not settings.get('evolution_api_key'):
            logger.warning("Evolution API não configurada")
            return

        # Pedido explícito de humano -> transfere na hora
        if detect_human_request(text):
            await db.leads.update_one(
                {"id": lead_doc['id']},
                {"$set": {
                    "human_takeover": True,
                    "meta_data.transfer_reason": "pedido_do_cliente",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }}
            )
            await db.events.insert_one(Event(
                lead_id=lead_doc['id'], event_type="transferido_para_humano",
                metadata={"motivo": "pedido_do_cliente"}
            ).model_dump())

            aviso = "Claro! Já estou chamando um especialista pra falar com você agora mesmo."
            await db.messages.insert_one(Message(
                lead_id=lead_doc['id'], role=MessageRole.AGENT, content=aviso
            ).model_dump())
            await send_whatsapp_message(
                settings['evolution_api_url'], settings['evolution_api_key'],
                settings.get('evolution_instance', 'default'), phone, aviso
            )
            return

        # Qualificação invisível
        qual_result = await analyze_qualification_ai(
            text, lead_doc.get('criteria_met', {}), settings.get('qualification_rules', {})
        )

        new_score = lead_doc.get('score', 0) + qual_result['score_delta']
        new_criteria = qual_result['criteria_met']

        temperature = 'cold'
        if new_score >= 30:
            temperature = 'warm'
        if new_score >= 60:
            temperature = 'hot'

        new_stage = lead_doc.get('stage', 'new')
        min_score = settings.get('qualification_rules', {}).get('min_score_qualified', 50)

        if new_stage == 'new' and new_score > 0:
            new_stage = 'in_progress'

        if new_score >= min_score and new_stage in ('new', 'in_progress'):
            new_stage = 'qualified'
            if settings.get('meta_pixel_id') and settings.get('meta_capi_token'):
                await send_event(
                    settings['meta_pixel_id'], settings['meta_capi_token'],
                    EVENT_MAPPING.get('lead_qualified', 'Lead'), phone
                )
            await db.events.insert_one(Event(
                lead_id=lead_doc['id'], event_type="lead_qualificado", metadata={"score": new_score}
            ).model_dump())

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

        lead_doc.update({
            "score": new_score, "criteria_met": new_criteria,
            "temperature": temperature, "stage": new_stage
        })

        messages = await db.messages.find(
            {"lead_id": lead_doc['id']}, {"_id": 0}
        ).sort("timestamp", 1).to_list(50)

        playbook_context = await get_active_playbook_context(db)

        response_text = await generate_response(
            [{'role': m['role'], 'content': m['content']} for m in messages],
            settings.get('system_prompt', ''),
            lead_doc,
            playbook_context,
        )

        await db.messages.insert_one(Message(
            lead_id=lead_doc['id'], role=MessageRole.AGENT, content=response_text
        ).model_dump())

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
        event = payload.get('event', '')
        logger.info(f"Webhook recebido: {event}")

        if event.replace('_', '.') not in ['messages.upsert', 'message', 'messages']:
            return {"status": "ignored", "event": event}

        msg_data = extract_message_from_webhook(payload)
        if not msg_data:
            return {"status": "no_message"}

        # Ignora mensagens enviadas pela própria instância
        if payload.get('data', {}).get('key', {}).get('fromMe'):
            return {"status": "ignored_from_me"}

        background_tasks.add_task(
            process_incoming_message, msg_data['phone'], msg_data['text'], msg_data['name']
        )
        return {"status": "processing"}

    except Exception as e:
        logger.error(f"Erro webhook: {e}")
        return {"status": "error", "detail": str(e)}

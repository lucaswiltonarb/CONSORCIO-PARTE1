# Serviço Meta CAPI - Conversions API
import httpx
import hashlib
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

META_GRAPH_URL = "https://graph.facebook.com/v18.0"

def hash_data(value: str) -> str:
    """Hash SHA256 para dados do usuário"""
    return hashlib.sha256(value.lower().strip().encode()).hexdigest()

async def send_event(
    pixel_id: str,
    access_token: str,
    event_name: str,
    phone: str,
    event_data: Optional[Dict[str, Any]] = None
) -> bool:
    """Envia evento para Meta Conversions API"""
    try:
        if not pixel_id or not access_token:
            logger.warning("Meta CAPI não configurado")
            return False
        
        url = f"{META_GRAPH_URL}/{pixel_id}/events"
        
        # Formata telefone para hash
        clean_phone = ''.join(filter(str.isdigit, phone))
        if not clean_phone.startswith('55'):
            clean_phone = f"55{clean_phone}"
        
        event = {
            "event_name": event_name,
            "event_time": int(datetime.now(timezone.utc).timestamp()),
            "action_source": "system_generated",
            "user_data": {
                "ph": [hash_data(clean_phone)],
                "country": [hash_data("br")]
            }
        }
        
        if event_data:
            event["custom_data"] = event_data
        
        payload = {
            "data": [event],
            "access_token": access_token
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"Evento {event_name} enviado para Meta")
            return True
            
    except Exception as e:
        logger.error(f"Erro Meta CAPI: {e}")
        return False

# Mapeamento de eventos internos para Meta
EVENT_MAPPING = {
    "lead_qualified": "Lead",
    "negotiation_started": "InitiateCheckout",
    "documentation_requested": "AddToCart",
    "sale_confirmed": "Purchase"
}

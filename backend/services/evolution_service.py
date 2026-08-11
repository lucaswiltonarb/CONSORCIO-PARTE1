# Serviço Evolution API - WhatsApp
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

async def send_whatsapp_message(api_url: str, api_key: str, instance: str, phone: str, message: str) -> bool:
    """Envia mensagem via Evolution API"""
    try:
        url = f"{api_url.rstrip('/')}/message/sendText/{instance}"
        
        headers = {
            "Content-Type": "application/json",
            "apikey": api_key
        }
        
        # Formata número (remove caracteres especiais)
        clean_phone = ''.join(filter(str.isdigit, phone))
        if not clean_phone.startswith('55'):
            clean_phone = f"55{clean_phone}"
        
        payload = {
            "number": clean_phone,
            "text": message
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"Mensagem enviada para {phone}")
            return True
            
    except Exception as e:
        logger.error(f"Erro ao enviar WhatsApp: {e}")
        return False

def extract_message_from_webhook(data: dict) -> Optional[dict]:
    """Extrai dados da mensagem do webhook Evolution"""
    try:
        # Estrutura padrão Evolution API
        message_data = data.get('data', {})
        
        # Tenta diferentes estruturas
        if 'message' in message_data:
            msg = message_data['message']
            text = msg.get('conversation') or msg.get('extendedTextMessage', {}).get('text', '')
        else:
            text = message_data.get('body', '') or message_data.get('text', '')
        
        phone = message_data.get('key', {}).get('remoteJid', '').replace('@s.whatsapp.net', '')
        if not phone:
            phone = message_data.get('from', '').replace('@s.whatsapp.net', '')
        
        name = message_data.get('pushName', '') or message_data.get('name', '')
        
        if not text or not phone:
            return None
            
        return {
            'phone': phone,
            'text': text,
            'name': name
        }
        
    except Exception as e:
        logger.error(f"Erro ao extrair mensagem: {e}")
        return None

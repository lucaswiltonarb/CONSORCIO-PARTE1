# Serviço de IA - Claude Sonnet 5
import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

EMERGENT_KEY = os.environ.get('EMERGENT_API_KEY', '')

async def generate_response(messages_history: List[Dict], system_prompt: str, lead_context: Dict[str, Any]) -> str:
    """Gera resposta usando Claude Sonnet 5 via Emergent"""
    try:
        from emergentintegrations.llm.anthropic import AnthropicConfig, chat_completion
        
        config = AnthropicConfig(
            api_key=EMERGENT_KEY,
            model="claude-sonnet-4-20250514"
        )
        
        # Monta contexto do lead
        context_info = f"""
Contexto do Lead:
- Nome: {lead_context.get('name', 'Não informado')}
- Telefone: {lead_context.get('phone', '')}
- Estágio: {lead_context.get('stage', 'new')}
- Score: {lead_context.get('score', 0)}
- Temperatura: {lead_context.get('temperature', 'cold')}
- Critérios atendidos: {lead_context.get('criteria_met', {})}
"""
        
        full_system = f"{system_prompt}\n\n{context_info}"
        
        # Formata mensagens para API
        formatted_messages = []
        for msg in messages_history[-20:]:  # Últimas 20 mensagens
            role = "user" if msg.get('role') == 'lead' else "assistant"
            formatted_messages.append({
                "role": role,
                "content": msg.get('content', '')
            })
        
        response = await chat_completion(
            config=config,
            system_prompt=full_system,
            user_message=formatted_messages[-1]['content'] if formatted_messages else "",
            conversation_history=formatted_messages[:-1] if len(formatted_messages) > 1 else []
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Erro Claude: {e}")
        return "Desculpe, tive um problema técnico. Um atendente vai entrar em contato em breve."

def analyze_qualification(message: str, current_criteria: Dict[str, bool], rules: Dict) -> Dict[str, Any]:
    """Analisa mensagem e atualiza critérios de qualificação"""
    message_lower = message.lower()
    updated = current_criteria.copy()
    score_delta = 0
    
    criteria_list = rules.get('criteria', [])
    
    for criterion in criteria_list:
        key = criterion['key']
        keyword = criterion.get('question', '').lower()
        weight = criterion.get('weight', 10)
        
        if keyword and keyword in message_lower and not updated.get(key):
            # Análise simples de sentimento positivo
            positive_indicators = ['sim', 'tenho', 'posso', 'quero', 'ok', 'certo', 'claro']
            if any(ind in message_lower for ind in positive_indicators):
                updated[key] = True
                score_delta += weight
    
    return {
        'criteria_met': updated,
        'score_delta': score_delta
    }

# Serviço de IA - Claude Sonnet 5 via Emergent LLM Key
import os
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

EMERGENT_KEY = os.environ.get('EMERGENT_LLM_KEY') or os.environ.get('EMERGENT_API_KEY', '')
MODEL = "claude-sonnet-5"

REGRAS_FIXAS = """
REGRAS INVIOLÁVEIS:
1. NUNCA confirme, feche ou aprove uma venda. Apenas um atendente humano pode confirmar vendas.
2. Nunca diga que a venda está fechada, aprovada ou confirmada.
3. Qualifique o cliente de forma invisível: nunca faça interrogatório nem liste perguntas.
4. Uma pergunta por vez, no ritmo natural da conversa.
5. Se o cliente pedir para falar com humano/atendente/pessoa, responda que já está chamando um especialista.
6. Nunca invente valores, taxas ou prazos que não estejam no seu contexto.
7. Mensagens curtas, tom de WhatsApp, sem formatação robótica e sem emojis em excesso.
"""


async def generate_response(
    messages_history: List[Dict],
    system_prompt: str,
    lead_context: Dict[str, Any],
    playbook_context: str = "",
) -> str:
    """Gera resposta do agente usando Claude Sonnet 5"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        contexto_lead = f"""
CONTEXTO DO LEAD:
- Nome: {lead_context.get('name') or 'não informado'}
- Telefone: {lead_context.get('phone', '')}
- Estágio no funil: {lead_context.get('stage', 'new')}
- Score de qualificação: {lead_context.get('score', 0)}
- Temperatura: {lead_context.get('temperature', 'cold')}
- Critérios já atendidos: {lead_context.get('criteria_met', {})}
- Documentos solicitados: {lead_context.get('documents_requested', [])}
- Documentos recebidos: {lead_context.get('documents_received', [])}
"""

        full_system = f"{system_prompt}\n{REGRAS_FIXAS}\n{contexto_lead}"
        if playbook_context:
            full_system += f"\n\nPLAYBOOK DOS ESPECIALISTAS (aprenda o tom e as abordagens que funcionam):\n{playbook_context[:8000]}"

        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"lead_{lead_context.get('id', 'sem_id')}",
            system_message=full_system,
        ).with_model("anthropic", MODEL)

        historico = []
        for msg in messages_history[-20:]:
            papel = "Cliente" if msg.get('role') == 'lead' else "Você"
            historico.append(f"{papel}: {msg.get('content', '')}")

        prompt = "Histórico da conversa:\n" + "\n".join(historico) + \
            "\n\nResponda APENAS com a próxima mensagem a ser enviada ao cliente no WhatsApp."

        resposta = await chat.send_message(UserMessage(text=prompt))
        return (resposta or "").strip()

    except Exception as e:
        logger.error(f"Erro Claude: {e}")
        return "Tive uma instabilidade aqui, já estou chamando um especialista pra te atender."


async def generate_playbook(conversas_texto: str) -> str:
    """Extrai um playbook de vendas a partir de conversas históricas de especialistas"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id="treinamento_playbook",
            system_message=(
                "Você analisa conversas reais de especialistas em consórcio no WhatsApp e extrai um "
                "playbook prático de vendas em português do Brasil."
            ),
        ).with_model("anthropic", MODEL)

        prompt = f"""Analise as conversas abaixo e produza um playbook objetivo com:
1. TOM DE VOZ (como o especialista fala)
2. ABERTURAS que funcionam (exemplos reais resumidos)
3. PERGUNTAS DE QUALIFICAÇÃO usadas de forma natural
4. OBJEÇÕES mais comuns e respostas que funcionaram
5. FRASES DE AVANÇO para levar o cliente à documentação
6. O QUE EVITAR

Seja direto, use bullets curtos. Máximo 900 palavras.

CONVERSAS:
{conversas_texto[:60000]}"""

        resposta = await chat.send_message(UserMessage(text=prompt))
        return (resposta or "").strip()

    except Exception as e:
        logger.error(f"Erro gerando playbook: {e}")
        return ""


async def analyze_qualification_ai(mensagem: str, criterios_atuais: Dict[str, bool], regras: Dict) -> Dict[str, Any]:
    """Qualificação assistida por IA com fallback por palavras-chave"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import json

        criterios = regras.get('criteria', [])
        lista = "\n".join([f"- {c['key']}: {c.get('question', '')} (peso {c.get('weight', 10)})" for c in criterios])

        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id="qualificacao",
            system_message="Você classifica mensagens de leads. Responda SOMENTE com JSON válido.",
        ).with_model("anthropic", MODEL)

        prompt = f"""Critérios de qualificação:
{lista}

Critérios já atendidos: {json.dumps(criterios_atuais)}

Mensagem do lead: "{mensagem}"

Responda com JSON: {{"criterios_atendidos": ["chave1", "chave2"]}} contendo apenas os critérios NOVOS que esta mensagem comprova."""

        raw = await chat.send_message(UserMessage(text=prompt))
        texto = (raw or "").strip()
        if "```" in texto:
            texto = texto.split("```")[1].replace("json", "", 1).strip()
        data = json.loads(texto)

        atualizados = dict(criterios_atuais)
        delta = 0
        pesos = {c['key']: c.get('weight', 10) for c in criterios}
        for chave in data.get('criterios_atendidos', []):
            if chave in pesos and not atualizados.get(chave):
                atualizados[chave] = True
                delta += pesos[chave]

        return {'criteria_met': atualizados, 'score_delta': delta}

    except Exception as e:
        logger.warning(f"Qualificação IA falhou, usando fallback: {e}")
        return analyze_qualification(mensagem, criterios_atuais, regras)


def analyze_qualification(message: str, current_criteria: Dict[str, bool], rules: Dict) -> Dict[str, Any]:
    """Qualificação simples por palavras-chave (fallback)"""
    message_lower = message.lower()
    updated = dict(current_criteria)
    score_delta = 0

    for criterion in rules.get('criteria', []):
        key = criterion['key']
        keyword = (criterion.get('question') or '').lower()
        weight = criterion.get('weight', 10)
        if keyword and keyword in message_lower and not updated.get(key):
            positivos = ['sim', 'tenho', 'posso', 'quero', 'ok', 'certo', 'claro', 'consigo']
            if any(ind in message_lower for ind in positivos):
                updated[key] = True
                score_delta += weight

    return {'criteria_met': updated, 'score_delta': score_delta}


def detect_human_request(message: str) -> bool:
    """Detecta pedido explícito de atendimento humano"""
    texto = message.lower()
    gatilhos = [
        'falar com humano', 'falar com atendente', 'falar com uma pessoa', 'atendente humano',
        'quero falar com alguem', 'quero falar com alguém', 'me transfere', 'falar com consultor',
        'falar com especialista', 'falar com gerente', 'pessoa real'
    ]
    return any(g in texto for g in gatilhos)

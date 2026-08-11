# Modelos de dados - PROMPT MESTRE
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from uuid import uuid4
from enum import Enum

class FunnelStage(str, Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    QUALIFIED = "qualified"
    NEGOTIATION = "negotiation"
    DOCUMENTATION = "documentation"
    CONFIRMED = "confirmed"  # Apenas manual
    LOST = "lost"

class MessageRole(str, Enum):
    LEAD = "lead"
    AGENT = "agent"  # IA
    HUMAN = "human"  # Atendente humano

class Lead(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    phone: str
    name: Optional[str] = None
    score: int = 0
    stage: FunnelStage = FunnelStage.NEW
    temperature: str = "cold"  # cold, warm, hot
    origin: Optional[str] = None
    criteria_met: Dict[str, bool] = {}
    documents_requested: List[str] = []
    documents_received: List[str] = []
    human_takeover: bool = False
    assigned_to: Optional[str] = None
    meta_data: Dict[str, Any] = {}
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class LeadCreate(BaseModel):
    phone: str
    name: Optional[str] = None
    origin: Optional[str] = None

class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    lead_id: str
    role: MessageRole
    content: str
    context_state: Dict[str, Any] = {}
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class MessageCreate(BaseModel):
    lead_id: str
    role: MessageRole
    content: str

class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    lead_id: str
    event_type: str
    metadata: Dict[str, Any] = {}
    synced_to_meta: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class Settings(BaseModel):
    id: str = "main_settings"
    meta_capi_token: Optional[str] = None
    meta_pixel_id: Optional[str] = None
    evolution_api_url: Optional[str] = None
    evolution_api_key: Optional[str] = None
    evolution_instance: Optional[str] = None
    qualification_rules: Dict[str, Any] = {
        "min_score_qualified": 50,
        "criteria": [
            {"key": "has_income", "weight": 20, "question": "renda"},
            {"key": "has_interest", "weight": 15, "question": "interesse"},
            {"key": "has_documents", "weight": 25, "question": "documentos"},
            {"key": "budget_fit", "weight": 20, "question": "orçamento"},
            {"key": "timeline_ready", "weight": 20, "question": "prazo"}
        ]
    }
    system_prompt: str = """Você é um especialista em consórcios. Seja natural, amigável e direto.
Nunca use estruturas robóticas. Fale como um humano experiente.
Seu objetivo é qualificar leads de forma invisível, entendendo suas necessidades.
NUNCA confirme vendas - apenas humanos podem fazer isso.
Se o cliente pedir para falar com humano, transfira imediatamente."""
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class SettingsUpdate(BaseModel):
    meta_capi_token: Optional[str] = None
    meta_pixel_id: Optional[str] = None
    evolution_api_url: Optional[str] = None
    evolution_api_key: Optional[str] = None
    evolution_instance: Optional[str] = None
    qualification_rules: Optional[Dict[str, Any]] = None
    system_prompt: Optional[str] = None

# Webhook Evolution API
class EvolutionWebhook(BaseModel):
    event: str
    instance: str
    data: Dict[str, Any]

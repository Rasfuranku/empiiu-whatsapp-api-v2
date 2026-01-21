from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class BusinessCategory(str, Enum):
    IDEATION = "IDEATION"
    MARKET = "MARKET"
    FINANCIALS = "FINANCIALS"
    TEAM = "TEAM"
    COMPLETED = "COMPLETED"

class EntrepreneurState(BaseModel):
    entrepreneur_id: str
    current_category: BusinessCategory = BusinessCategory.IDEATION
    profile_data: Dict[str, Any] = Field(default_factory=dict)
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    last_message: Optional[str] = None
    question_count: int = 0

# WhatsApp Webhook Schemas
class WhatsAppMessage(BaseModel):
    from_number: str = Field(alias="from")
    id: str
    timestamp: str
    text: Dict[str, str] = Field(default_factory=lambda: {"body": ""})
    type: str = "text"

class WhatsAppValue(BaseModel):
    messaging_product: str = "whatsapp"
    metadata: Dict[str, str]
    contacts: List[Dict[str, Any]] = []
    messages: List[WhatsAppMessage] = []

class WhatsAppChange(BaseModel):
    value: WhatsAppValue
    field: str = "messages"

class WhatsAppEntry(BaseModel):
    id: str
    changes: List[WhatsAppChange] = []

class WhatsAppWebhookPayload(BaseModel):
    object: str = "whatsapp_business_account"
    entry: List[WhatsAppEntry] = []

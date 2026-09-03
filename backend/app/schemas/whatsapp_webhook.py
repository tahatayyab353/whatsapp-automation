from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class WebhookMetadata(BaseModel):
    display_phone_number: Optional[str] = Field(None, description="Display phone number of the Meta business account")
    phone_number_id: Optional[str] = Field(None, description="Meta Phone Number ID used for tenant routing")

    model_config = ConfigDict(extra="ignore")


class WebhookProfile(BaseModel):
    name: Optional[str] = Field(None, description="Customer profile name in WhatsApp")

    model_config = ConfigDict(extra="ignore")


class WebhookContact(BaseModel):
    wa_id: Optional[str] = Field(None, description="Customer WhatsApp ID")
    profile: Optional[WebhookProfile] = Field(None, description="Customer profile information")

    model_config = ConfigDict(extra="ignore")


class WebhookText(BaseModel):
    body: Optional[str] = Field(None, description="Message text content")

    model_config = ConfigDict(extra="ignore")


class WebhookIncomingMessage(BaseModel):
    id: Optional[str] = Field(None, description="Meta unique message ID (e.g. wamid.XXX)")
    from_: Optional[str] = Field(None, alias="from", description="Customer phone number")
    timestamp: Optional[str] = Field(None, description="Unix timestamp of message")
    type: Optional[str] = Field(None, description="Message type: text, image, audio, etc.")
    text: Optional[WebhookText] = Field(None, description="Text object containing body if type == 'text'")

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class WebhookValue(BaseModel):
    messaging_product: Optional[str] = Field(None, description="Messaging product name ('whatsapp')")
    metadata: Optional[WebhookMetadata] = Field(None, description="Phone number metadata")
    contacts: Optional[List[WebhookContact]] = Field(None, description="Customer contact info if present")
    messages: Optional[List[WebhookIncomingMessage]] = Field(None, description="Incoming messages list if present")
    statuses: Optional[List[Dict[str, Any]]] = Field(None, description="Delivery receipts if present")

    model_config = ConfigDict(extra="ignore")


class WebhookChange(BaseModel):
    field: Optional[str] = Field(None, description="Field name (e.g. 'messages')")
    value: Optional[WebhookValue] = Field(None, description="Event change payload")

    model_config = ConfigDict(extra="ignore")


class WebhookEntry(BaseModel):
    id: Optional[str] = Field(None, description="WhatsApp Business Account (WABA) ID")
    changes: List[WebhookChange] = Field(default_factory=list, description="Array of change objects")

    model_config = ConfigDict(extra="ignore")


class WebhookPayload(BaseModel):
    object: str = Field(..., description="Top-level event object (expected: 'whatsapp_business_account')")
    entry: List[WebhookEntry] = Field(default_factory=list, description="Array of event entries")

    model_config = ConfigDict(extra="ignore")


class WebhookStatusResponse(BaseModel):
    status: str = Field("ok", description="Status acknowledgment")

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class WhatsAppMessageItem(BaseModel):
    id: str = Field(..., description="Meta unique message ID for the outbound message (e.g. wamid.HBgM...)")

    model_config = ConfigDict(extra="ignore")


class WhatsAppContactItem(BaseModel):
    input: Optional[str] = Field(None, description="Recipient phone number as submitted")
    wa_id: Optional[str] = Field(None, description="WhatsApp ID of recipient")

    model_config = ConfigDict(extra="ignore")


class WhatsAppSendMessageResponse(BaseModel):
    messaging_product: str = Field("whatsapp", description="Messaging product name")
    contacts: Optional[List[WhatsAppContactItem]] = Field(default_factory=list, description="Recipient contacts")
    messages: List[WhatsAppMessageItem] = Field(default_factory=list, description="List of created message objects")

    model_config = ConfigDict(extra="ignore")


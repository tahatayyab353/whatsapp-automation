import uuid
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class ConversationBase(BaseModel):
    lead_id: Optional[uuid.UUID] = Field(None, description="Associated Lead identifier")
    channel: Literal["whatsapp", "website", "instagram", "other"] = Field(
        "whatsapp", description="Communication channel"
    )
    external_conversation_id: Optional[str] = Field(
        None, max_length=255, description="External channel conversation identifier"
    )


class ConversationCreate(ConversationBase):
    pass


class ConversationUpdate(BaseModel):
    status: Literal["open", "human_required", "closed"] = Field(
        ..., description="New conversation operational status"
    )


class ConversationRead(BaseModel):
    id: uuid.UUID
    clinic_id: uuid.UUID
    lead_id: Optional[uuid.UUID] = None
    channel: str
    external_conversation_id: Optional[str] = None
    status: str
    started_at: datetime
    last_message_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

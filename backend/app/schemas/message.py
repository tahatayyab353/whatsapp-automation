import uuid
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class MessageBase(BaseModel):
    sender_type: Literal["customer", "ai", "staff", "system"] = Field(
        ..., description="Originator role of the message"
    )
    message_type: Literal["text", "image", "audio", "document", "other"] = Field(
        "text", description="Payload content type"
    )
    content: str = Field(..., description="Message text or media caption")
    external_message_id: Optional[str] = Field(
        None, max_length=255, description="External message provider ID"
    )


class MessageCreate(MessageBase):
    pass


class MessageRead(BaseModel):
    id: uuid.UUID
    clinic_id: uuid.UUID
    conversation_id: uuid.UUID
    sender_type: str
    message_type: str
    content: str
    external_message_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

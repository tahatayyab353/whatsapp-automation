import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class WhatsAppAccountBase(BaseModel):
    clinic_id: uuid.UUID
    phone_number: str
    phone_number_id: str
    business_account_id: Optional[str] = None
    is_active: bool = True


class WhatsAppAccountRead(WhatsAppAccountBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


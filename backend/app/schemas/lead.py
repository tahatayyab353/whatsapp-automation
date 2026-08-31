import uuid
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class LeadBase(BaseModel):
    full_name: str = Field(..., max_length=255, description="Patient full name")
    phone: str = Field(..., max_length=50, description="Patient telephone / WhatsApp number")
    email: Optional[str] = Field(None, max_length=255, description="Patient email address")
    source: Literal["whatsapp", "website", "instagram", "manual", "other"] = Field(
        "whatsapp", description="Lead origination channel"
    )
    status: Literal[
        "new", "contacted", "qualified", "appointment_requested", "booked", "converted", "lost"
    ] = Field("new", description="Current lead status")
    service_interest: Optional[str] = Field(None, max_length=255, description="Requested treatment or service")
    notes: Optional[str] = Field(None, description="Staff / intake notes")


class LeadCreate(LeadBase):
    pass


class LeadUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255, description="Patient full name")
    phone: Optional[str] = Field(None, max_length=50, description="Patient telephone / WhatsApp number")
    email: Optional[str] = Field(None, max_length=255, description="Patient email address")
    source: Optional[Literal["whatsapp", "website", "instagram", "manual", "other"]] = Field(
        None, description="Lead origination channel"
    )
    status: Optional[
        Literal["new", "contacted", "qualified", "appointment_requested", "booked", "converted", "lost"]
    ] = Field(None, description="Current lead status")
    service_interest: Optional[str] = Field(None, max_length=255, description="Requested treatment or service")
    notes: Optional[str] = Field(None, description="Staff / intake notes")


class LeadRead(BaseModel):
    id: uuid.UUID
    clinic_id: uuid.UUID
    full_name: str
    phone: str
    email: Optional[str] = None
    source: str
    status: str
    service_interest: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

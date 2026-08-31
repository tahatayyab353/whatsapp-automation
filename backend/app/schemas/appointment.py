import uuid
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class AppointmentBase(BaseModel):
    lead_id: Optional[uuid.UUID] = Field(None, description="Patient Lead identifier")
    conversation_id: Optional[uuid.UUID] = Field(None, description="Originating conversation identifier")
    scheduled_at: datetime = Field(..., description="Timezone-aware appointment scheduled datetime")
    status: Literal["requested", "confirmed", "cancelled", "completed", "no_show"] = Field(
        "requested", description="Appointment status"
    )
    notes: Optional[str] = Field(None, description="Consultation notes or instructions")


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentUpdate(BaseModel):
    scheduled_at: Optional[datetime] = Field(None, description="Timezone-aware appointment scheduled datetime")
    status: Optional[
        Literal["requested", "confirmed", "cancelled", "completed", "no_show"]
    ] = Field(None, description="Appointment status")
    notes: Optional[str] = Field(None, description="Consultation notes or instructions")


class AppointmentRead(BaseModel):
    id: uuid.UUID
    clinic_id: uuid.UUID
    lead_id: Optional[uuid.UUID] = None
    conversation_id: Optional[uuid.UUID] = None
    scheduled_at: datetime
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

import uuid
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

AppointmentStatus = Literal[
    "requested",
    "confirmed",
    "cancelled",
    "completed",
    "no_show",
    "rescheduled",
]


class AppointmentBase(BaseModel):
    lead_id: Optional[uuid.UUID] = Field(None, description="Patient Lead identifier")
    conversation_id: Optional[uuid.UUID] = Field(None, description="Originating conversation identifier")
    title: str = Field("Consultation", max_length=255, description="Appointment title or procedure")
    description: Optional[str] = Field(None, description="Appointment description or patient symptoms")
    scheduled_at: datetime = Field(..., description="Timezone-aware appointment scheduled datetime")
    duration_minutes: int = Field(30, ge=5, le=480, description="Duration in minutes (5 to 480)")
    timezone: str = Field("Asia/Karachi", max_length=50, description="Operating timezone")
    status: AppointmentStatus = Field("requested", description="Appointment status")
    notes: Optional[str] = Field(None, description="Internal staff notes or instructions")


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255, description="Appointment title or procedure")
    description: Optional[str] = Field(None, description="Appointment description or patient symptoms")
    scheduled_at: Optional[datetime] = Field(None, description="Timezone-aware appointment scheduled datetime")
    duration_minutes: Optional[int] = Field(None, ge=5, le=480, description="Duration in minutes (5 to 480)")
    timezone: Optional[str] = Field(None, max_length=50, description="Operating timezone")
    status: Optional[AppointmentStatus] = Field(None, description="Appointment status")
    notes: Optional[str] = Field(None, description="Internal staff notes or instructions")


class AppointmentActionRequest(BaseModel):
    notes: Optional[str] = Field(None, description="Optional action notes or instructions")


class AppointmentStatusUpdate(BaseModel):
    status: Optional[AppointmentStatus] = Field(None, description="Target appointment status")
    notes: Optional[str] = Field(None, description="Optional transition notes or cancellation reason")


class AppointmentCancelRequest(BaseModel):
    reason: Optional[str] = Field(None, description="Reason for cancellation")


class AppointmentRead(BaseModel):
    id: uuid.UUID
    clinic_id: uuid.UUID
    lead_id: Optional[uuid.UUID] = None
    conversation_id: Optional[uuid.UUID] = None
    created_by_user_id: Optional[uuid.UUID] = None
    title: str
    description: Optional[str] = None
    scheduled_at: datetime
    duration_minutes: int
    timezone: str
    status: str
    notes: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

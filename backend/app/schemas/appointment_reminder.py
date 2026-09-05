import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class AppointmentReminderBase(BaseModel):
    reminder_type: str = Field(..., description="Type of reminder: APPOINTMENT_24H or APPOINTMENT_2H")
    scheduled_for: datetime = Field(..., description="Scheduled delivery timestamp (UTC)")
    status: str = Field("pending", description="Status: pending, processing, sent, failed, cancelled")


class AppointmentReminderRead(BaseModel):
    id: uuid.UUID
    clinic_id: uuid.UUID
    appointment_id: uuid.UUID
    reminder_type: str
    scheduled_for: datetime
    status: str
    attempts: int
    max_attempts: int
    last_attempt_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    provider_message_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppointmentReminderSummary(BaseModel):
    reminder_24h_status: Optional[str] = None
    reminder_24h_scheduled_for: Optional[datetime] = None
    reminder_24h_sent_at: Optional[datetime] = None
    reminder_2h_status: Optional[str] = None
    reminder_2h_scheduled_for: Optional[datetime] = None
    reminder_2h_sent_at: Optional[datetime] = None

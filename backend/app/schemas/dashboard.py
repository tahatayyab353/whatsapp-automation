import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DashboardMetrics(BaseModel):
    total_leads: int = Field(0, description="Total active leads for the clinic")
    open_conversations: int = Field(0, description="Active unclosed conversation threads")
    pending_handoffs: int = Field(0, description="Human handoffs awaiting staff assignment/resolution")
    today_appointments: int = Field(0, description="Appointments scheduled for today")
    confirmed_appointments_today: int = Field(0, description="Confirmed appointments scheduled for today")
    completed_appointments_today: int = Field(0, description="Completed appointments today")
    new_leads_today: int = Field(0, description="Leads created today")


class DashboardAppointmentItem(BaseModel):
    id: uuid.UUID
    lead_id: Optional[uuid.UUID] = None
    lead_name: Optional[str] = None
    lead_phone: Optional[str] = None
    title: str
    scheduled_at: datetime
    duration_minutes: int
    status: str
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DashboardHandoffItem(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    lead_id: Optional[uuid.UUID] = None
    lead_name: Optional[str] = None
    lead_phone: Optional[str] = None
    reason: str
    status: str
    notes: Optional[str] = None
    requested_at: datetime
    assigned_to_user_id: Optional[uuid.UUID] = None
    assigned_to_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DashboardConversationItem(BaseModel):
    id: uuid.UUID
    lead_id: Optional[uuid.UUID] = None
    lead_name: Optional[str] = None
    lead_phone: Optional[str] = None
    channel: str
    status: str
    last_message_at: Optional[datetime] = None
    last_message_preview: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DashboardLeadItem(BaseModel):
    id: uuid.UUID
    full_name: Optional[str] = None
    phone: str
    email: Optional[str] = None
    status: str
    service_interest: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DashboardSummaryResponse(BaseModel):
    clinic_id: uuid.UUID
    clinic_name: str
    timezone: str
    metrics: DashboardMetrics
    today_appointments: List[DashboardAppointmentItem]
    pending_handoffs: List[DashboardHandoffItem]
    recent_conversations: List[DashboardConversationItem]
    recent_leads: List[DashboardLeadItem]


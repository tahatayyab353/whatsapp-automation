import uuid
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

HandoffStatus = Literal["pending", "assigned", "resolved", "cancelled"]
HandoffReason = Literal[
    "customer_requested_human",
    "complex_question",
    "complaint",
    "billing_issue",
    "urgent_request",
    "ai_uncertain",
    "staff_required",
    "other",
]


class HandoffCreate(BaseModel):
    conversation_id: uuid.UUID
    reason: HandoffReason = Field("staff_required", description="Reason for escalation")
    notes: Optional[str] = Field(None, description="Contextual notes or summary")


class HandoffAssign(BaseModel):
    assigned_to_user_id: Optional[uuid.UUID] = Field(
        None, description="Staff user ID to assign to. If omitted, assigns to current user."
    )


class HandoffResolve(BaseModel):
    notes: Optional[str] = Field(None, description="Resolution notes")


class HandoffRead(BaseModel):
    id: uuid.UUID
    clinic_id: uuid.UUID
    conversation_id: uuid.UUID
    lead_id: Optional[uuid.UUID] = None
    assigned_to_user_id: Optional[uuid.UUID] = None
    status: str
    reason: str
    notes: Optional[str] = None
    requested_at: datetime
    assigned_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StaffMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4096, description="Staff reply message to send on WhatsApp")


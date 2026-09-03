from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class ExtractedLeadData(BaseModel):
    """
    Structured schema for AI lead extraction and qualification.
    Strictly validated before updating CRM database records.
    """
    full_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Customer full name if explicitly stated in conversation",
    )
    email: Optional[str] = Field(
        None,
        max_length=255,
        description="Customer email address if explicitly stated in conversation",
    )
    phone: Optional[str] = Field(
        None,
        max_length=50,
        description="Informational phone number mentioned in text (does NOT override canonical WhatsApp phone)",
    )
    service_interest: Optional[str] = Field(
        None,
        max_length=255,
        description="Specific service, procedure, or treatment requested",
    )
    intent: Optional[Literal["low", "medium", "high"]] = Field(
        None,
        description="Customer intent level: low (casual/checking), medium (inquiry/availability), high (ready to book/urgent)",
    )
    urgency: Optional[Literal["low", "medium", "high"]] = Field(
        None,
        description="Customer urgency level: low (routine), medium (near-term), high (emergency/severe pain/immediate)",
    )
    notes: Optional[str] = Field(
        None,
        description="Brief qualification notes and context",
    )
    status: Optional[
        Literal["new", "contacted", "qualified", "appointment_requested", "booked", "converted", "lost"]
    ] = Field(
        None,
        description="Recommended lead status based on conversation context",
    )

    model_config = ConfigDict(extra="ignore")


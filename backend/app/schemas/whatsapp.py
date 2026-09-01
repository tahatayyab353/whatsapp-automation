import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class WhatsAppAccountBase(BaseModel):
    phone_number: str = Field(..., max_length=50, description="E.164 formatted WhatsApp phone number")
    phone_number_id: str = Field(..., max_length=100, description="Meta WhatsApp Phone Number ID")
    business_account_id: Optional[str] = Field(None, max_length=100, description="Meta WhatsApp Business Account ID")
    display_name: Optional[str] = Field(None, max_length=255, description="Clinic WhatsApp profile display name")
    is_active: bool = Field(True, description="Whether the WhatsApp integration is active")


class WhatsAppAccountCreate(BaseModel):
    phone_number: str = Field(..., max_length=50, description="E.164 formatted WhatsApp phone number (e.g. +923001234567)")
    phone_number_id: str = Field(..., max_length=100, description="Meta WhatsApp Phone Number ID")
    business_account_id: Optional[str] = Field(None, max_length=100, description="Meta WhatsApp Business Account ID")
    display_name: Optional[str] = Field(None, max_length=255, description="Clinic WhatsApp profile display name")
    access_token: Optional[str] = Field(None, max_length=500, description="Per-clinic Meta Cloud API System User Access Token")


class WhatsAppAccountUpdate(BaseModel):
    phone_number: Optional[str] = Field(None, max_length=50, description="E.164 formatted WhatsApp phone number")
    phone_number_id: Optional[str] = Field(None, max_length=100, description="Meta WhatsApp Phone Number ID")
    business_account_id: Optional[str] = Field(None, max_length=100, description="Meta WhatsApp Business Account ID")
    display_name: Optional[str] = Field(None, max_length=255, description="Clinic WhatsApp profile display name")
    access_token: Optional[str] = Field(None, max_length=500, description="New Meta Cloud API Access Token to replace existing")
    is_active: Optional[bool] = Field(None, description="Active status")


class WhatsAppAccountRead(BaseModel):
    """
    Public representation of a clinic's WhatsApp Account.
    SECURITY: The `access_token` is STRICTLY EXCLUDED and never returned.
    """
    id: uuid.UUID
    clinic_id: uuid.UUID
    phone_number: str
    phone_number_id: str
    business_account_id: Optional[str] = None
    display_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

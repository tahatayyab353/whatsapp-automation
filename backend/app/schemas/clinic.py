import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ClinicBase(BaseModel):
    name: str = Field(..., max_length=255, description="Clinic business name")
    slug: str = Field(..., max_length=100, description="Clinic URL slug")
    description: Optional[str] = Field(None, description="Clinic overview and description")
    phone: Optional[str] = Field(None, max_length=50, description="Clinic contact telephone")
    email: Optional[str] = Field(None, max_length=255, description="Clinic contact email")
    website: Optional[str] = Field(None, max_length=255, description="Clinic official website URL")
    timezone: str = Field("Asia/Karachi", max_length=50, description="Operating timezone")
    is_active: bool = Field(True, description="Active status")


class ClinicUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255, description="Clinic business name")
    description: Optional[str] = Field(None, description="Clinic overview and description")
    phone: Optional[str] = Field(None, max_length=50, description="Clinic contact telephone")
    email: Optional[str] = Field(None, max_length=255, description="Clinic contact email")
    website: Optional[str] = Field(None, max_length=255, description="Clinic official website URL")
    timezone: Optional[str] = Field(None, max_length=50, description="Operating timezone")


class ClinicRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    timezone: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

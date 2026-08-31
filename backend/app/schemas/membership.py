import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class MemberRead(BaseModel):
    id: uuid.UUID = Field(..., description="Membership identifier")
    user_id: uuid.UUID = Field(..., description="Platform User identifier")
    email: str = Field(..., description="User email address")
    full_name: str = Field(..., description="User full name")
    role: str = Field(..., description="Assigned clinic role (owner, admin, staff)")
    is_active: bool = Field(..., description="User account active status")
    created_at: datetime = Field(..., description="Membership join date")

    model_config = ConfigDict(from_attributes=True)


class MemberRoleUpdate(BaseModel):
    role: Literal["owner", "admin", "staff"] = Field(..., description="New clinic role to assign")


class ClinicMembershipBase(BaseModel):
    clinic_id: uuid.UUID
    user_id: uuid.UUID
    role: str = "staff"


class ClinicMembershipRead(ClinicMembershipBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

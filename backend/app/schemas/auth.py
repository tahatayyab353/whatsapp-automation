from typing import Optional
from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password (minimum 8 characters)")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        clean = v.strip().lower()
        if "@" not in clean or "." not in clean.split("@")[-1]:
            raise ValueError("Invalid email address format.")
        return clean


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token validity in seconds")


class AuthenticatedTestResponse(BaseModel):
    authenticated: bool = True
    user_id: str
    email: str


class ClinicContextTestResponse(BaseModel):
    authorized: bool = True
    clinic_id: str
    role: str


class RoleTestResponse(BaseModel):
    authorized: bool = True
    role: str
    user_id: str


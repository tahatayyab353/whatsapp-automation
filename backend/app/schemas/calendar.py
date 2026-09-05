from datetime import datetime
from typing import List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class CalendarConnectionResponse(BaseModel):
    """
    Public representation of a clinic calendar connection.
    Strictly excludes access tokens, refresh tokens, and credentials.
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clinic_id: uuid.UUID
    provider: str
    account_identifier: Optional[str] = None
    calendar_identifier: Optional[str] = "primary"
    calendar_name: Optional[str] = None
    status: str
    last_error: Optional[str] = None
    connected_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class CalendarConnectResponse(BaseModel):
    """
    Response returned when initiating OAuth authorization.
    """
    authorization_url: str
    provider: str


class CalendarItemResponse(BaseModel):
    """
    Item representation of an available calendar on Google or Microsoft.
    """
    id: str
    name: str
    primary: bool = False
    description: Optional[str] = None


class CalendarSelectRequest(BaseModel):
    """
    Request payload to choose target calendar identifier.
    """
    provider: str
    calendar_identifier: str = Field(..., min_length=1, description="Calendar ID in external provider")
    calendar_name: Optional[str] = Field(None, description="Human readable calendar name")


class CalendarSyncResponse(BaseModel):
    """
    Response returned on manual sync trigger.
    """
    processed_count: int
    status: str = "ok"


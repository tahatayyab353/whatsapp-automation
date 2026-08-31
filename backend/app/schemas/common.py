from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class MessageResponse(BaseModel):
    """
    Standard simple message response.
    """
    message: str = Field(..., description="Response message")


class HealthResponse(BaseModel):
    """
    Standard health check response.
    """
    status: str = Field("ok", description="Service health status")


class SystemInfoResponse(BaseModel):
    """
    Safe, non-sensitive system information.
    """
    name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Active runtime environment")


class ErrorBody(BaseModel):
    """
    Structured error response payload.
    """
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error explanation")
    details: Optional[Any] = Field(None, description="Additional context or validation errors")


class ErrorResponse(BaseModel):
    """
    Top-level wrapper for error responses.
    """
    error: ErrorBody


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Standard pagination response wrapper.
    """
    items: List[T] = Field(..., description="List of paginated items")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items per page")
    total: int = Field(..., description="Total number of items matching filter")

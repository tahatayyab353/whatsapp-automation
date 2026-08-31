import uuid
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class KnowledgeDocumentBase(BaseModel):
    title: str = Field(..., max_length=255, description="Document or FAQ title")
    content: str = Field(..., description="Full text document or answer content")
    category: Optional[
        Literal["faq", "service", "pricing", "doctor", "location", "policy", "general"]
    ] = Field("general", description="Content classification")
    is_active: bool = Field(True, description="Active status for retrieval")


class KnowledgeCreate(KnowledgeDocumentBase):
    pass


class KnowledgeUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255, description="Document or FAQ title")
    content: Optional[str] = Field(None, description="Full text document or answer content")
    category: Optional[
        Literal["faq", "service", "pricing", "doctor", "location", "policy", "general"]
    ] = Field(None, description="Content classification")
    is_active: Optional[bool] = Field(None, description="Active status for retrieval")


class KnowledgeDocumentRead(BaseModel):
    id: uuid.UUID
    clinic_id: uuid.UUID
    title: str
    content: str
    category: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

import uuid
from typing import Optional
from pydantic import BaseModel, Field
from app.ai.types import AIUsage


class AIChatRequest(BaseModel):
    conversation_id: uuid.UUID = Field(..., description="Active conversation identifier")
    message: str = Field(..., min_length=1, max_length=2000, description="Customer message text")


class AIChatResponse(BaseModel):
    content: str = Field(..., description="Generated AI receptionist response")
    provider: str = Field(..., description="AI provider that generated this completion")
    model: str = Field(..., description="Model identifier used")
    usage: Optional[AIUsage] = Field(None, description="Token consumption metrics if reported")


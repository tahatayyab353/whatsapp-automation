from dataclasses import dataclass
from typing import Optional
from pydantic import BaseModel, Field


class AIUsage(BaseModel):
    input_tokens: Optional[int] = Field(None, description="Number of prompt tokens consumed")
    output_tokens: Optional[int] = Field(None, description="Number of completion tokens generated")
    total_tokens: Optional[int] = Field(None, description="Total tokens consumed")


class AIResponse(BaseModel):
    content: str = Field(..., description="Generated text response")
    provider: str = Field(..., description="Name of the AI provider that generated this response")
    model: str = Field(..., description="Model identifier used")
    usage: Optional[AIUsage] = Field(None, description="Token usage metrics if available")


@dataclass
class ChatMessage:
    role: str
    content: str


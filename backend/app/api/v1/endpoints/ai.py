from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.exceptions import (
    AIAuthenticationError,
    AIConfigurationError,
    AIProviderError,
)
from app.ai.receptionist import receptionist_service
from app.api.deps import ClinicContext, require_staff
from app.db.database import get_db
from app.models import Conversation, Message
from app.schemas.ai import AIChatRequest, AIChatResponse

router = APIRouter()


@router.post(
    "/test-chat",
    response_model=AIChatResponse,
    summary="[DEV/TEST] Test AI Receptionist Completion",
    description="Development endpoint for testing the AI Receptionist engine with Gemini primary and Groq fallback. Persists customer message and generated AI reply.",
)
async def test_ai_chat(
    payload: AIChatRequest,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> AIChatResponse:
    # 1. Verify conversation belongs strictly to active clinic
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == payload.conversation_id,
            Conversation.clinic_id == clinic_context.clinic.id,
        )
    )
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found for this clinic.",
        )

    now = datetime.now(timezone.utc)

    # 2. Ingest incoming customer message
    customer_msg = Message(
        clinic_id=clinic_context.clinic.id,
        conversation_id=conversation.id,
        sender_type="customer",
        message_type="text",
        content=payload.message,
        created_at=now,
    )
    db.add(customer_msg)
    db.commit()

    # 3. Generate AI response with primary/fallback orchestration
    try:
        ai_response = await receptionist_service.generate_receptionist_response(
            db=db,
            clinic=clinic_context.clinic,
            conversation=conversation,
            customer_message_text=payload.message,
        )
    except AIConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI service is misconfigured or missing credentials.",
        ) from exc
    except AIAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI provider authentication failed.",
        ) from exc
    except AIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI receptionist service is temporarily unavailable.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI receptionist service is temporarily unavailable.",
        ) from exc

    # 4. Ingest generated AI message
    ai_msg_time = datetime.now(timezone.utc)
    ai_msg = Message(
        clinic_id=clinic_context.clinic.id,
        conversation_id=conversation.id,
        sender_type="ai",
        message_type="text",
        content=ai_response.content,
        created_at=ai_msg_time,
    )
    conversation.last_message_at = ai_msg_time

    db.add(ai_msg)
    db.add(conversation)
    db.commit()

    return AIChatResponse(
        content=ai_response.content,
        provider=ai_response.provider,
        model=ai_response.model,
        usage=ai_response.usage,
    )


import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import ClinicContext, require_staff
from app.db.database import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.message import MessageCreate, MessageRead
from app.services.message_service import message_service

router = APIRouter()


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageRead,
    summary="Create Message",
    description="Sends a new message in a conversation. Scoped strictly to the active clinic.",
)
async def create_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> MessageRead:
    msg = message_service.create_message(
        db=db,
        clinic_id=clinic_context.clinic.id,
        conversation_id=conversation_id,
        payload=payload,
    )
    return MessageRead.model_validate(msg)


@router.get(
    "/{conversation_id}/messages",
    response_model=PaginatedResponse[MessageRead],
    summary="List Conversation Messages",
    description="Retrieves messages for a conversation ordered chronologically.",
)
async def list_messages(
    conversation_id: uuid.UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page (max 100)"),
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> PaginatedResponse[MessageRead]:
    items, total = message_service.list_messages(
        db=db,
        clinic_id=clinic_context.clinic.id,
        conversation_id=conversation_id,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse[MessageRead](
        items=[MessageRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


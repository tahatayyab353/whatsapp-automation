import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import ClinicContext, require_staff
from app.db.database import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.conversation import ConversationCreate, ConversationRead, ConversationUpdate
from app.services.conversation_service import conversation_service

router = APIRouter()


@router.post(
    "",
    response_model=ConversationRead,
    summary="Create Conversation",
    description="Initiates a conversation thread associated with the active clinic tenant.",
)
async def create_conversation(
    payload: ConversationCreate,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> ConversationRead:
    conv = conversation_service.create_conversation(db, clinic_context.clinic.id, payload)
    return ConversationRead.model_validate(conv)


@router.get(
    "",
    response_model=PaginatedResponse[ConversationRead],
    summary="List Conversations",
    description="Retrieves a paginated list of conversations for the active clinic.",
)
async def list_conversations(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    status: Optional[str] = Query(None, description="Filter by status (open, human_required, closed)"),
    channel: Optional[str] = Query(None, description="Filter by channel (whatsapp, website, instagram, other)"),
    search: Optional[str] = Query(None, description="Search by external conversation ID"),
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ConversationRead]:
    items, total = conversation_service.list_conversations(
        db=db,
        clinic_id=clinic_context.clinic.id,
        page=page,
        page_size=page_size,
        conv_status=status,
        channel=channel,
        search=search,
    )
    return PaginatedResponse[ConversationRead](
        items=[ConversationRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationRead,
    summary="Get Conversation Details",
    description="Fetches details of a specific conversation thread belonging to the active clinic.",
)
async def get_conversation(
    conversation_id: uuid.UUID,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> ConversationRead:
    conv = conversation_service.get_conversation(db, clinic_context.clinic.id, conversation_id)
    return ConversationRead.model_validate(conv)


@router.patch(
    "/{conversation_id}",
    response_model=ConversationRead,
    summary="Update Conversation Status",
    description="Updates conversation operational status (e.g. open, human_required, closed).",
)
async def update_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> ConversationRead:
    updated = conversation_service.update_conversation(
        db=db,
        clinic_id=clinic_context.clinic.id,
        conversation_id=conversation_id,
        payload=payload,
    )
    return ConversationRead.model_validate(updated)


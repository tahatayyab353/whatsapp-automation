import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import ClinicContext, require_staff
from app.db.database import get_db
from app.schemas.handoff import (
    HandoffAssign,
    HandoffCreate,
    HandoffRead,
    HandoffResolve,
    StaffMessageCreate,
)
from app.schemas.message import MessageRead
from app.services.handoff_service import handoff_service

router = APIRouter()


@router.get(
    "/handoffs",
    response_model=List[HandoffRead],
    summary="List Human Handoffs",
    description="Retrieves escalations and handoffs for the active clinic. Permitted for Owner, Admin, and Staff.",
)
async def list_handoffs(
    status: Optional[str] = Query(None, description="Filter by status (pending, assigned, resolved, cancelled)"),
    skip: int = Query(0, ge=0, description="Pagination skip"),
    limit: int = Query(50, ge=1, le=100, description="Pagination limit"),
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> List[HandoffRead]:
    handoffs = handoff_service.list_handoffs(
        db=db,
        clinic_id=clinic_context.clinic.id,
        status=status,
        skip=skip,
        limit=limit,
    )
    return [HandoffRead.model_validate(h) for h in handoffs]


@router.post(
    "/handoffs",
    response_model=HandoffRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Human Handoff",
    description="Escalates a conversation to human staff intervention. Permitted for Owner, Admin, and Staff.",
)
async def create_handoff(
    payload: HandoffCreate,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> HandoffRead:
    handoff = handoff_service.request_handoff(
        db=db,
        clinic_id=clinic_context.clinic.id,
        conversation_id=payload.conversation_id,
        reason=payload.reason,
        notes=payload.notes,
    )
    return HandoffRead.model_validate(handoff)


@router.get(
    "/handoffs/{handoff_id}",
    response_model=HandoffRead,
    summary="Get Handoff Details",
    description="Retrieves details of a specific handoff escalation. Permitted for Owner, Admin, and Staff.",
)
async def get_handoff(
    handoff_id: uuid.UUID,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> HandoffRead:
    handoff = handoff_service.get_handoff(
        db=db,
        clinic_id=clinic_context.clinic.id,
        handoff_id=handoff_id,
    )
    return HandoffRead.model_validate(handoff)


@router.post(
    "/handoffs/{handoff_id}/assign",
    response_model=HandoffRead,
    summary="Claim or Assign Handoff",
    description="Claims or assigns a pending handoff to a staff member. Permitted for Owner, Admin, and Staff.",
)
async def assign_handoff(
    handoff_id: uuid.UUID,
    payload: Optional[HandoffAssign] = None,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> HandoffRead:
    assignee_id = (
        payload.assigned_to_user_id
        if payload and payload.assigned_to_user_id
        else clinic_context.user.id
    )
    handoff = handoff_service.assign_handoff(
        db=db,
        clinic_id=clinic_context.clinic.id,
        handoff_id=handoff_id,
        user_id=assignee_id,
    )
    return HandoffRead.model_validate(handoff)


@router.post(
    "/handoffs/{handoff_id}/resolve",
    response_model=HandoffRead,
    summary="Resolve Handoff",
    description="Resolves a human handoff and resets conversation status so AI can respond to future inquiries. Permitted for Owner, Admin, and Staff.",
)
async def resolve_handoff(
    handoff_id: uuid.UUID,
    payload: Optional[HandoffResolve] = None,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> HandoffRead:
    notes = payload.notes if payload else None
    handoff = handoff_service.resolve_handoff(
        db=db,
        clinic_id=clinic_context.clinic.id,
        handoff_id=handoff_id,
        notes=notes,
    )
    return HandoffRead.model_validate(handoff)


@router.post(
    "/handoffs/{handoff_id}/cancel",
    response_model=HandoffRead,
    summary="Cancel Handoff",
    description="Cancels a human handoff. Permitted for Owner, Admin, and Staff.",
)
async def cancel_handoff(
    handoff_id: uuid.UUID,
    payload: Optional[HandoffResolve] = None,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> HandoffRead:
    notes = payload.notes if payload else None
    handoff = handoff_service.cancel_handoff(
        db=db,
        clinic_id=clinic_context.clinic.id,
        handoff_id=handoff_id,
        notes=notes,
    )
    return HandoffRead.model_validate(handoff)


@router.post(
    "/handoffs/{handoff_id}/messages",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Send Staff Reply on WhatsApp",
    description="Sends an outbound staff message directly to the customer on WhatsApp. Permitted for Owner, Admin, and Staff.",
)
async def send_staff_message_on_handoff(
    handoff_id: uuid.UUID,
    payload: StaffMessageCreate,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> MessageRead:
    handoff = handoff_service.get_handoff(
        db=db,
        clinic_id=clinic_context.clinic.id,
        handoff_id=handoff_id,
    )
    message = await handoff_service.send_staff_message(
        db=db,
        clinic_id=clinic_context.clinic.id,
        conversation_id=handoff.conversation_id,
        staff_user_id=clinic_context.user.id,
        content=payload.content,
    )
    return MessageRead.model_validate(message)


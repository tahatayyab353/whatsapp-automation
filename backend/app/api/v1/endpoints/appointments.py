import uuid
from datetime import date, datetime
from typing import Optional
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import ClinicContext, require_staff
from app.db.database import get_db
from app.schemas.appointment import (
    AppointmentActionRequest,
    AppointmentCancelRequest,
    AppointmentCreate,
    AppointmentRead,
    AppointmentStatusUpdate,
    AppointmentUpdate,
)
from app.schemas.appointment_reminder import AppointmentReminderRead
from app.schemas.common import PaginatedResponse
from app.services.appointment_service import appointment_service
from app.services.reminder_service import reminder_service

router = APIRouter()



@router.post(
    "",
    response_model=AppointmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Appointment",
    description="Schedules a new patient appointment for the active clinic. Permitted for Owner, Admin, and Staff.",
)
async def create_appointment(
    payload: AppointmentCreate,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> AppointmentRead:
    appointment = appointment_service.create_appointment(
        db=db,
        clinic_id=clinic_context.clinic.id,
        payload=payload,
        created_by_user_id=clinic_context.user.id,
    )
    return AppointmentRead.model_validate(appointment)


@router.get(
    "",
    response_model=PaginatedResponse[AppointmentRead],
    summary="List Appointments",
    description="Retrieves a paginated list of appointments for the active clinic with optional date, lead, and status filters.",
)
async def list_appointments(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    status: Optional[str] = Query(None, description="Filter by status (requested, confirmed, cancelled, completed, no_show, rescheduled)"),
    lead_id: Optional[uuid.UUID] = Query(None, description="Filter by patient lead ID"),
    conversation_id: Optional[uuid.UUID] = Query(None, description="Filter by conversation ID"),
    target_date: Optional[date] = Query(None, alias="date", description="Filter for a specific date (YYYY-MM-DD)"),
    date_from: Optional[datetime] = Query(None, description="Filter appointments from this UTC timestamp"),
    date_to: Optional[datetime] = Query(None, description="Filter appointments up to this UTC timestamp"),
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> PaginatedResponse[AppointmentRead]:
    items, total = appointment_service.list_appointments(
        db=db,
        clinic_id=clinic_context.clinic.id,
        page=page,
        page_size=page_size,
        status=status,
        lead_id=lead_id,
        conversation_id=conversation_id,
        target_date=target_date,
        date_from=date_from,
        date_to=date_to,
    )
    return PaginatedResponse[AppointmentRead](
        items=[AppointmentRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/{appointment_id}",
    response_model=AppointmentRead,
    summary="Get Appointment Details",
    description="Fetches details of a specific appointment belonging to the active clinic.",
)
async def get_appointment(
    appointment_id: uuid.UUID,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> AppointmentRead:
    appointment = appointment_service.get_appointment(
        db=db,
        clinic_id=clinic_context.clinic.id,
        appointment_id=appointment_id,
    )
    return AppointmentRead.model_validate(appointment)


@router.patch(
    "/{appointment_id}",
    response_model=AppointmentRead,
    summary="Update Appointment",
    description="Updates appointment time, duration, status, or notes for the active clinic.",
)
async def update_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentUpdate,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> AppointmentRead:
    updated = appointment_service.update_appointment(
        db=db,
        clinic_id=clinic_context.clinic.id,
        appointment_id=appointment_id,
        payload=payload,
    )
    return AppointmentRead.model_validate(updated)


@router.post(
    "/{appointment_id}/confirm",
    response_model=AppointmentRead,
    summary="Confirm Appointment",
    description="Confirms a requested appointment booking.",
)
async def confirm_appointment(
    appointment_id: uuid.UUID,
    payload: Optional[AppointmentActionRequest] = None,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> AppointmentRead:
    notes = payload.notes if payload else None
    confirmed = appointment_service.confirm_appointment(
        db=db,
        clinic_id=clinic_context.clinic.id,
        appointment_id=appointment_id,
        notes=notes,
    )
    return AppointmentRead.model_validate(confirmed)


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentRead,
    summary="Cancel Appointment",
    description="Cancels an appointment and records cancellation timestamp.",
)
async def cancel_appointment(
    appointment_id: uuid.UUID,
    payload: Optional[AppointmentCancelRequest] = None,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> AppointmentRead:
    reason = payload.reason if payload else None
    cancelled = appointment_service.cancel_appointment(
        db=db,
        clinic_id=clinic_context.clinic.id,
        appointment_id=appointment_id,
        reason=reason,
    )
    return AppointmentRead.model_validate(cancelled)


@router.post(
    "/{appointment_id}/complete",
    response_model=AppointmentRead,
    summary="Complete Appointment",
    description="Marks a confirmed appointment as completed.",
)
async def complete_appointment(
    appointment_id: uuid.UUID,
    payload: Optional[AppointmentActionRequest] = None,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> AppointmentRead:
    notes = payload.notes if payload else None
    completed = appointment_service.complete_appointment(
        db=db,
        clinic_id=clinic_context.clinic.id,
        appointment_id=appointment_id,
        notes=notes,
    )
    return AppointmentRead.model_validate(completed)


@router.post(
    "/{appointment_id}/no-show",
    response_model=AppointmentRead,
    summary="Mark Appointment No-Show",
    description="Marks a confirmed appointment as patient no-show.",
)
async def mark_appointment_no_show(
    appointment_id: uuid.UUID,
    payload: Optional[AppointmentActionRequest] = None,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> AppointmentRead:
    notes = payload.notes if payload else None
    no_show = appointment_service.mark_no_show(
        db=db,
        clinic_id=clinic_context.clinic.id,
        appointment_id=appointment_id,
        notes=notes,
    )
    return AppointmentRead.model_validate(no_show)


@router.get(
    "/{appointment_id}/reminders",
    response_model=List[AppointmentReminderRead],
    summary="Get Appointment Reminders",
    description="Fetches all reminder delivery logs and statuses for a specific appointment.",
)
async def get_appointment_reminders(
    appointment_id: uuid.UUID,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> List[AppointmentReminderRead]:
    # Validate appointment belongs to active clinic
    appointment_service.get_appointment(
        db=db,
        clinic_id=clinic_context.clinic.id,
        appointment_id=appointment_id,
    )
    reminders = reminder_service.get_reminders_for_appointment(
        db=db,
        clinic_id=clinic_context.clinic.id,
        appointment_id=appointment_id,
    )
    return [AppointmentReminderRead.model_validate(r) for r in reminders]


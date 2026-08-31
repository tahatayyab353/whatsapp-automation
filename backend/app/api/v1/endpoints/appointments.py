import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import ClinicContext, require_staff
from app.db.database import get_db
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentRead,
    AppointmentUpdate,
)
from app.schemas.common import PaginatedResponse
from app.services.appointment_service import appointment_service

router = APIRouter()


@router.post(
    "",
    response_model=AppointmentRead,
    summary="Create Appointment",
    description="Schedules a new patient appointment for the active clinic.",
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
    )
    return AppointmentRead.model_validate(appointment)


@router.get(
    "",
    response_model=PaginatedResponse[AppointmentRead],
    summary="List Appointments",
    description="Retrieves a paginated list of appointments for the active clinic with optional date and status filters.",
)
async def list_appointments(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    status: Optional[str] = Query(None, description="Filter by status (requested, confirmed, cancelled, completed, no_show)"),
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
        app_status=status,
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
    description="Updates appointment time, status, or notes for the active clinic.",
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


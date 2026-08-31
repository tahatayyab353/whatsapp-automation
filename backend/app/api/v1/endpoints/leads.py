import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import ClinicContext, require_staff
from app.db.database import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.lead import LeadCreate, LeadRead, LeadUpdate
from app.services.lead_service import lead_service

router = APIRouter()


@router.post(
    "",
    response_model=LeadRead,
    summary="Create Lead",
    description="Registers a new patient inquiry or lead. Clinic ID is derived automatically from context.",
)
async def create_lead(
    payload: LeadCreate,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> LeadRead:
    lead = lead_service.create_lead(db, clinic_context.clinic.id, payload)
    return LeadRead.model_validate(lead)


@router.get(
    "",
    response_model=PaginatedResponse[LeadRead],
    summary="List Leads",
    description="Retrieves a paginated list of leads for the active clinic with optional filtering.",
)
async def list_leads(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    status: Optional[str] = Query(None, description="Filter by lead status"),
    source: Optional[str] = Query(None, description="Filter by lead source"),
    search: Optional[str] = Query(None, description="Search by name, phone, or email"),
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> PaginatedResponse[LeadRead]:
    items, total = lead_service.list_leads(
        db=db,
        clinic_id=clinic_context.clinic.id,
        page=page,
        page_size=page_size,
        lead_status=status,
        source=source,
        search=search,
    )
    return PaginatedResponse[LeadRead](
        items=[LeadRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/{lead_id}",
    response_model=LeadRead,
    summary="Get Lead Details",
    description="Fetches full details of a specific lead belonging to the active clinic.",
)
async def get_lead(
    lead_id: uuid.UUID,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> LeadRead:
    lead = lead_service.get_lead(db, clinic_context.clinic.id, lead_id)
    return LeadRead.model_validate(lead)


@router.patch(
    "/{lead_id}",
    response_model=LeadRead,
    summary="Update Lead",
    description="Updates lead status, details, or notes. Scoped to the active clinic.",
)
async def update_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdate,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> LeadRead:
    updated = lead_service.update_lead(db, clinic_context.clinic.id, lead_id, payload)
    return LeadRead.model_validate(updated)


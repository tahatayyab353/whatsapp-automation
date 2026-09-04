from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import ClinicContext, require_staff
from app.db.database import get_db
from app.schemas.dashboard import DashboardSummaryResponse
from app.services.dashboard_service import dashboard_service

router = APIRouter()


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    summary="Get Clinic Operations Dashboard Summary",
    description="Retrieves aggregated operational metrics, today's appointments, pending handoffs, recent conversations, and leads for the active clinic.",
)
async def get_dashboard_summary(
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> DashboardSummaryResponse:
    return dashboard_service.get_summary(
        db=db,
        clinic_id=clinic_context.clinic.id,
    )


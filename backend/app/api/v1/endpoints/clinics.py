from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import ClinicContext, get_current_clinic, require_admin
from app.db.database import get_db
from app.schemas.clinic import ClinicRead, ClinicUpdate
from app.services.clinic_service import clinic_service

router = APIRouter()


@router.get(
    "/me",
    response_model=ClinicRead,
    summary="Get Clinic Profile",
    description="Returns the profile and settings for the authenticated clinic tenant context.",
)
async def get_clinic_me(
    clinic_context: ClinicContext = Depends(get_current_clinic),
) -> ClinicRead:
    return ClinicRead.model_validate(clinic_service.get_profile(clinic_context.clinic))


@router.patch(
    "/me",
    response_model=ClinicRead,
    summary="Update Clinic Profile",
    description="Updates clinic settings. Permitted for clinic Owner and Admin roles.",
)
async def update_clinic_me(
    payload: ClinicUpdate,
    clinic_context: ClinicContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ClinicRead:
    updated = clinic_service.update_profile(db, clinic_context.clinic, payload)
    return ClinicRead.model_validate(updated)


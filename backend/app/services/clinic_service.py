from sqlalchemy.orm import Session

from app.models import Clinic
from app.schemas.clinic import ClinicUpdate


class ClinicService:
    @staticmethod
    def get_profile(clinic: Clinic) -> Clinic:
        return clinic

    @staticmethod
    def update_profile(db: Session, clinic: Clinic, payload: ClinicUpdate) -> Clinic:
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(clinic, field, value)
        db.add(clinic)
        db.commit()
        db.refresh(clinic)
        return clinic


clinic_service = ClinicService()


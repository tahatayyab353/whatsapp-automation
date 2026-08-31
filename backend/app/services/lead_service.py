import uuid
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Lead
from app.schemas.lead import LeadCreate, LeadUpdate


class LeadService:
    @staticmethod
    def create_lead(db: Session, clinic_id: uuid.UUID, payload: LeadCreate) -> Lead:
        lead = Lead(
            clinic_id=clinic_id,
            full_name=payload.full_name,
            phone=payload.phone,
            email=payload.email,
            source=payload.source,
            status=payload.status,
            service_interest=payload.service_interest,
            notes=payload.notes,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return lead

    @staticmethod
    def list_leads(
        db: Session,
        clinic_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        lead_status: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[Lead], int]:
        stmt = select(Lead).where(Lead.clinic_id == clinic_id)

        if lead_status:
            stmt = stmt.where(Lead.status == lead_status)
        if source:
            stmt = stmt.where(Lead.source == source)
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Lead.full_name.ilike(pattern),
                    Lead.phone.ilike(pattern),
                    Lead.email.ilike(pattern),
                )
            )

        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        offset = (page - 1) * page_size
        items = db.scalars(
            stmt.order_by(Lead.created_at.desc()).offset(offset).limit(page_size)
        ).all()

        return list(items), total

    @staticmethod
    def get_lead(db: Session, clinic_id: uuid.UUID, lead_id: uuid.UUID) -> Lead:
        lead = db.scalar(
            select(Lead).where(
                Lead.id == lead_id,
                Lead.clinic_id == clinic_id,
            )
        )
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lead not found.",
            )
        return lead

    @staticmethod
    def update_lead(
        db: Session,
        clinic_id: uuid.UUID,
        lead_id: uuid.UUID,
        payload: LeadUpdate,
    ) -> Lead:
        lead = LeadService.get_lead(db, clinic_id, lead_id)
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(lead, field, value)
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return lead


lead_service = LeadService()


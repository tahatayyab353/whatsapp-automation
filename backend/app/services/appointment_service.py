import uuid
from datetime import datetime
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Appointment, Conversation, Lead
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate


class AppointmentService:
    @staticmethod
    def create_appointment(
        db: Session,
        clinic_id: uuid.UUID,
        payload: AppointmentCreate,
    ) -> Appointment:
        if payload.lead_id:
            lead = db.scalar(
                select(Lead).where(
                    Lead.id == payload.lead_id,
                    Lead.clinic_id == clinic_id,
                )
            )
            if not lead:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Lead not found for this clinic.",
                )

        if payload.conversation_id:
            conv = db.scalar(
                select(Conversation).where(
                    Conversation.id == payload.conversation_id,
                    Conversation.clinic_id == clinic_id,
                )
            )
            if not conv:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found for this clinic.",
                )

        appointment = Appointment(
            clinic_id=clinic_id,
            lead_id=payload.lead_id,
            conversation_id=payload.conversation_id,
            scheduled_at=payload.scheduled_at,
            status=payload.status,
            notes=payload.notes,
        )
        db.add(appointment)
        db.commit()
        db.refresh(appointment)
        return appointment

    @staticmethod
    def list_appointments(
        db: Session,
        clinic_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        app_status: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Tuple[List[Appointment], int]:
        stmt = select(Appointment).where(Appointment.clinic_id == clinic_id)

        if app_status:
            stmt = stmt.where(Appointment.status == app_status)
        if date_from:
            stmt = stmt.where(Appointment.scheduled_at >= date_from)
        if date_to:
            stmt = stmt.where(Appointment.scheduled_at <= date_to)

        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        offset = (page - 1) * page_size
        items = db.scalars(
            stmt.order_by(Appointment.scheduled_at.asc()).offset(offset).limit(page_size)
        ).all()

        return list(items), total

    @staticmethod
    def get_appointment(
        db: Session,
        clinic_id: uuid.UUID,
        appointment_id: uuid.UUID,
    ) -> Appointment:
        appointment = db.scalar(
            select(Appointment).where(
                Appointment.id == appointment_id,
                Appointment.clinic_id == clinic_id,
            )
        )
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found.",
            )
        return appointment

    @staticmethod
    def update_appointment(
        db: Session,
        clinic_id: uuid.UUID,
        appointment_id: uuid.UUID,
        payload: AppointmentUpdate,
    ) -> Appointment:
        appointment = AppointmentService.get_appointment(db, clinic_id, appointment_id)
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(appointment, field, value)
        db.add(appointment)
        db.commit()
        db.refresh(appointment)
        return appointment


appointment_service = AppointmentService()


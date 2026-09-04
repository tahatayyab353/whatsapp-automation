import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, NotFoundException
from app.core.logging import logger
from app.models import Appointment, Clinic, Conversation, Lead
from app.models.base import utc_now
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate

# Valid State Transitions
VALID_TRANSITIONS = {
    "requested": {"confirmed", "cancelled", "rescheduled"},
    "confirmed": {"cancelled", "completed", "no_show", "rescheduled"},
    "rescheduled": {"confirmed", "cancelled"},
    "cancelled": set(),  # Terminal
    "completed": set(),  # Terminal
    "no_show": set(),    # Terminal
}


class AppointmentService:
    """
    Manages tenant-scoped patient appointments:
    booking requests, confirmation, rescheduling, cancellation, and completion.
    """

    @classmethod
    def create_appointment(
        cls,
        db: Session,
        clinic_id: uuid.UUID,
        payload: AppointmentCreate,
        created_by_user_id: Optional[uuid.UUID] = None,
    ) -> Appointment:
        # 1. Validate Lead if provided
        if payload.lead_id:
            lead = db.scalar(
                select(Lead).where(
                    Lead.id == payload.lead_id,
                    Lead.clinic_id == clinic_id,
                )
            )
            if not lead:
                raise NotFoundException("Lead not found for this clinic.")

        # 2. Validate Conversation if provided
        if payload.conversation_id:
            conv = db.scalar(
                select(Conversation).where(
                    Conversation.id == payload.conversation_id,
                    Conversation.clinic_id == clinic_id,
                )
            )
            if not conv:
                raise NotFoundException("Conversation not found for this clinic.")

        # 3. Validate scheduled_at not in past (with 5 min grace period for clock skew)
        now_utc = utc_now()
        scheduled_utc = payload.scheduled_at
        if scheduled_utc.tzinfo is None:
            scheduled_utc = scheduled_utc.replace(tzinfo=timezone.utc)

        if scheduled_utc < now_utc - timedelta(minutes=5):
            raise BadRequestException("Cannot schedule an appointment in the past.")

        # 4. Validate duration
        if payload.duration_minutes <= 0 or payload.duration_minutes > 480:
            raise BadRequestException("Duration must be between 5 and 480 minutes.")

        # 5. Resolve timezone from clinic if not specified
        tz = payload.timezone
        if not tz:
            clinic = db.scalar(select(Clinic).where(Clinic.id == clinic_id))
            tz = clinic.timezone if clinic and clinic.timezone else "Asia/Karachi"

        appointment = Appointment(
            clinic_id=clinic_id,
            lead_id=payload.lead_id,
            conversation_id=payload.conversation_id,
            created_by_user_id=created_by_user_id,
            title=payload.title or "Consultation",
            description=payload.description,
            scheduled_at=scheduled_utc,
            duration_minutes=payload.duration_minutes,
            timezone=tz,
            status=payload.status or "requested",
            notes=payload.notes,
        )
        db.add(appointment)
        db.commit()
        db.refresh(appointment)
        logger.info("Created appointment %s for clinic %s", appointment.id, clinic_id)
        return appointment

    @classmethod
    def get_appointment(
        cls,
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
            raise NotFoundException("Appointment not found.")
        return appointment

    @classmethod
    def list_appointments(
        cls,
        db: Session,
        clinic_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        lead_id: Optional[uuid.UUID] = None,
        conversation_id: Optional[uuid.UUID] = None,
        target_date: Optional[date] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Tuple[List[Appointment], int]:
        stmt = select(Appointment).where(Appointment.clinic_id == clinic_id)

        if status:
            stmt = stmt.where(Appointment.status == status)
        if lead_id:
            stmt = stmt.where(Appointment.lead_id == lead_id)
        if conversation_id:
            stmt = stmt.where(Appointment.conversation_id == conversation_id)
        if target_date:
            day_start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
            day_end = datetime.combine(target_date, time.max, tzinfo=timezone.utc)
            stmt = stmt.where(Appointment.scheduled_at >= day_start, Appointment.scheduled_at <= day_end)
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

    @classmethod
    def validate_status_transition(cls, current_status: str, new_status: str) -> None:
        if current_status == new_status:
            return
        allowed = VALID_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise BadRequestException(
                f"Invalid status transition from '{current_status}' to '{new_status}'."
            )

    @classmethod
    def update_appointment(
        cls,
        db: Session,
        clinic_id: uuid.UUID,
        appointment_id: uuid.UUID,
        payload: AppointmentUpdate,
    ) -> Appointment:
        appointment = cls.get_appointment(db, clinic_id, appointment_id)

        # Validate state transition if status is being updated
        if payload.status and payload.status != appointment.status:
            cls.validate_status_transition(appointment.status, payload.status)
            appointment.status = payload.status
            if payload.status == "cancelled" and not appointment.cancelled_at:
                appointment.cancelled_at = utc_now()

        # Validate scheduled_at if updating time
        if payload.scheduled_at:
            sched = payload.scheduled_at
            if sched.tzinfo is None:
                sched = sched.replace(tzinfo=timezone.utc)
            if sched < utc_now() - timedelta(minutes=5):
                raise BadRequestException("Cannot reschedule an appointment to the past.")
            appointment.scheduled_at = sched

        # Validate duration if updating
        if payload.duration_minutes is not None:
            if payload.duration_minutes <= 0 or payload.duration_minutes > 480:
                raise BadRequestException("Duration must be between 5 and 480 minutes.")
            appointment.duration_minutes = payload.duration_minutes

        if payload.title is not None:
            appointment.title = payload.title
        if payload.description is not None:
            appointment.description = payload.description
        if payload.timezone is not None:
            appointment.timezone = payload.timezone
        if payload.notes is not None:
            appointment.notes = payload.notes

        db.add(appointment)
        db.commit()
        db.refresh(appointment)
        logger.info("Updated appointment %s for clinic %s", appointment.id, clinic_id)
        return appointment

    @classmethod
    def confirm_appointment(
        cls,
        db: Session,
        clinic_id: uuid.UUID,
        appointment_id: uuid.UUID,
        notes: Optional[str] = None,
    ) -> Appointment:
        appointment = cls.get_appointment(db, clinic_id, appointment_id)
        cls.validate_status_transition(appointment.status, "confirmed")
        appointment.status = "confirmed"
        if notes:
            appointment.notes = f"{appointment.notes}\n[Confirmed] {notes}" if appointment.notes else f"[Confirmed] {notes}"
        db.add(appointment)
        db.commit()
        db.refresh(appointment)
        logger.info("Confirmed appointment %s", appointment.id)
        return appointment

    @classmethod
    def cancel_appointment(
        cls,
        db: Session,
        clinic_id: uuid.UUID,
        appointment_id: uuid.UUID,
        reason: Optional[str] = None,
    ) -> Appointment:
        appointment = cls.get_appointment(db, clinic_id, appointment_id)
        cls.validate_status_transition(appointment.status, "cancelled")
        appointment.status = "cancelled"
        appointment.cancelled_at = utc_now()
        if reason:
            appointment.notes = f"{appointment.notes}\n[Cancelled] {reason}" if appointment.notes else f"[Cancelled] {reason}"
        db.add(appointment)
        db.commit()
        db.refresh(appointment)
        logger.info("Cancelled appointment %s", appointment.id)
        return appointment

    @classmethod
    def complete_appointment(
        cls,
        db: Session,
        clinic_id: uuid.UUID,
        appointment_id: uuid.UUID,
        notes: Optional[str] = None,
    ) -> Appointment:
        appointment = cls.get_appointment(db, clinic_id, appointment_id)
        cls.validate_status_transition(appointment.status, "completed")
        appointment.status = "completed"
        if notes:
            appointment.notes = f"{appointment.notes}\n[Completed] {notes}" if appointment.notes else f"[Completed] {notes}"
        db.add(appointment)
        db.commit()
        db.refresh(appointment)
        logger.info("Completed appointment %s", appointment.id)
        return appointment

    @classmethod
    def mark_no_show(
        cls,
        db: Session,
        clinic_id: uuid.UUID,
        appointment_id: uuid.UUID,
        notes: Optional[str] = None,
    ) -> Appointment:
        appointment = cls.get_appointment(db, clinic_id, appointment_id)
        cls.validate_status_transition(appointment.status, "no_show")
        appointment.status = "no_show"
        if notes:
            appointment.notes = f"{appointment.notes}\n[No-Show] {notes}" if appointment.notes else f"[No-Show] {notes}"
        db.add(appointment)
        db.commit()
        db.refresh(appointment)
        logger.info("Marked appointment %s as no-show", appointment.id)
        return appointment

    @classmethod
    def create_appointment_request_from_ai(
        cls,
        db: Session,
        clinic_id: uuid.UUID,
        lead_id: Optional[uuid.UUID],
        conversation_id: Optional[uuid.UUID],
        scheduled_at: datetime,
        title: str = "Consultation Request",
        notes: Optional[str] = None,
    ) -> Appointment:
        """
        Idempotently creates or reuses an appointment request originating from AI receptionist / WhatsApp conversation.
        Prevents duplicate records from webhook retries or repeated customer statements.
        """
        # Check for existing active requested appointment for this conversation within ±2 hours of target time
        window_start = scheduled_at - timedelta(hours=2)
        window_end = scheduled_at + timedelta(hours=2)

        existing = None
        if conversation_id:
            existing = db.scalar(
                select(Appointment).where(
                    Appointment.clinic_id == clinic_id,
                    Appointment.conversation_id == conversation_id,
                    Appointment.status.in_(["requested", "confirmed"]),
                    Appointment.scheduled_at >= window_start,
                    Appointment.scheduled_at <= window_end,
                )
            )
        elif lead_id:
            existing = db.scalar(
                select(Appointment).where(
                    Appointment.clinic_id == clinic_id,
                    Appointment.lead_id == lead_id,
                    Appointment.status.in_(["requested", "confirmed"]),
                    Appointment.scheduled_at >= window_start,
                    Appointment.scheduled_at <= window_end,
                )
            )

        if existing:
            logger.info("Reusing existing appointment %s for conversation %s", existing.id, conversation_id)
            return existing

        payload = AppointmentCreate(
            lead_id=lead_id,
            conversation_id=conversation_id,
            title=title,
            scheduled_at=scheduled_at,
            status="requested",
            notes=notes,
        )
        return cls.create_appointment(db=db, clinic_id=clinic_id, payload=payload)


appointment_service = AppointmentService()

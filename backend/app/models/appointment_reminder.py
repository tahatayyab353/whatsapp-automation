import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic
    from app.models.appointment import Appointment


class AppointmentReminder(Base, TimestampMixin):
    """
    Tenant-Scoped Appointment Reminder Entity.
    Tracks scheduled, in-flight, sent, and failed 24h/2h notifications for appointments.
    Enforces idempotency and safe concurrent row claiming.
    """
    __tablename__ = "appointment_reminders"
    __table_args__ = (
        UniqueConstraint(
            "appointment_id",
            "reminder_type",
            name="uq_appointment_reminders_appt_type",
        ),
        Index(
            "ix_reminders_due_lookup",
            "clinic_id",
            "status",
            "scheduled_for",
        ),
        Index(
            "ix_reminders_appointment_type",
            "appointment_id",
            "reminder_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("appointments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    reminder_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Reminder type: APPOINTMENT_24H, APPOINTMENT_2H",
    )
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Target UTC timestamp when the reminder becomes eligible to send",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        index=True,
        nullable=False,
        comment="Status: pending, processing, sent, failed, cancelled",
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of delivery attempts made so far",
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
        comment="Maximum allowed retry attempts before permanent failure",
    )
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of the most recent delivery attempt",
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when successfully delivered to WhatsApp provider",
    )
    failed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when delivery permanently failed or max retries exceeded",
    )
    provider_message_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="External message ID returned by WhatsApp provider (e.g. wamid.xxx)",
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Categorical error code (e.g. RATE_LIMIT, NETWORK_ERROR, INVALID_CONTACT)",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Safe sanitized delivery failure message without secrets",
    )

    # Relationships
    clinic: Mapped["Clinic"] = relationship("Clinic")
    appointment: Mapped["Appointment"] = relationship("Appointment", back_populates="reminders")

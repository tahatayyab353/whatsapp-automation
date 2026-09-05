import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic
    from app.models.lead import Lead
    from app.models.conversation import Conversation
    from app.models.user import User
    from app.models.appointment_reminder import AppointmentReminder


class Appointment(Base, TimestampMixin):
    """
    Tenant-Scoped Appointment Entity.
    Tracks scheduled visits, consultations, and procedures for patients.
    Supports AI-requested booking requests and staff-confirmed appointments.
    """
    __tablename__ = "appointments"
    __table_args__ = (
        Index("ix_appointments_clinic_scheduled", "clinic_id", "scheduled_at"),
        Index("ix_appointments_clinic_status", "clinic_id", "status"),
        Index("ix_appointments_clinic_lead", "clinic_id", "lead_id"),
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
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        default="Consultation",
        nullable=False,
        comment="Appointment title or procedure name",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed description of appointment purpose or symptoms",
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
        comment="Timezone-aware appointment timestamp",
    )
    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
        comment="Duration in minutes (typically 15 to 240)",
    )
    timezone: Mapped[str] = mapped_column(
        String(50),
        default="Asia/Karachi",
        nullable=False,
        comment="Operating timezone for the scheduled appointment",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="requested",
        index=True,
        nullable=False,
        comment="Status: requested, confirmed, cancelled, completed, no_show, rescheduled",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Internal staff notes or instructions",
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when appointment was cancelled",
    )

    # Relationships
    clinic: Mapped["Clinic"] = relationship("Clinic", back_populates="appointments")
    lead: Mapped[Optional["Lead"]] = relationship("Lead", back_populates="appointments")
    conversation: Mapped[Optional["Conversation"]] = relationship("Conversation", back_populates="appointments")
    created_by: Mapped[Optional["User"]] = relationship("User")
    reminders: Mapped[List["AppointmentReminder"]] = relationship(
        "AppointmentReminder",
        back_populates="appointment",
        cascade="all, delete-orphan",
    )

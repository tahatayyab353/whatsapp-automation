import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic
    from app.models.lead import Lead
    from app.models.conversation import Conversation


class Appointment(Base, TimestampMixin):
    """
    Tenant-Scoped Appointment Entity.
    Tracks scheduled visits, consultations, and procedures.
    """
    __tablename__ = "appointments"
    __table_args__ = (
        Index("ix_appointments_clinic_scheduled", "clinic_id", "scheduled_at"),
        Index("ix_appointments_clinic_status", "clinic_id", "status"),
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
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
        comment="Timezone-aware appointment timestamp",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="requested",
        index=True,
        nullable=False,
        comment="Status: requested, confirmed, cancelled, completed, no_show",
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    clinic: Mapped["Clinic"] = relationship("Clinic", back_populates="appointments")
    lead: Mapped[Optional["Lead"]] = relationship("Lead", back_populates="appointments")
    conversation: Mapped[Optional["Conversation"]] = relationship("Conversation", back_populates="appointments")


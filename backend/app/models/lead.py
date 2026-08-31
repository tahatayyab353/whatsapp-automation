import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic
    from app.models.conversation import Conversation
    from app.models.appointment import Appointment


class Lead(Base, TimestampMixin):
    """
    Tenant-Scoped Lead Entity.
    Stores prospective patient details, interest, and qualification state.
    """
    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_clinic_phone", "clinic_id", "phone"),
        Index("ix_leads_clinic_status", "clinic_id", "status"),
        Index("ix_leads_clinic_created_at", "clinic_id", "created_at"),
    )

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(
        String(50),
        default="whatsapp",
        nullable=False,
        comment="Source: whatsapp, website, instagram, manual, other",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="new",
        index=True,
        nullable=False,
        comment="Status: new, contacted, qualified, appointment_requested, booked, converted, lost",
    )
    service_interest: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    clinic: Mapped["Clinic"] = relationship("Clinic", back_populates="leads")
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation",
        back_populates="lead",
    )
    appointments: Mapped[List["Appointment"]] = relationship(
        "Appointment",
        back_populates="lead",
    )


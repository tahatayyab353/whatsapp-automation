import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, utc_now

if TYPE_CHECKING:
    from app.models.clinic import Clinic
    from app.models.lead import Lead
    from app.models.message import Message
    from app.models.appointment import Appointment


class Conversation(Base, TimestampMixin):
    """
    Tenant-Scoped Conversation Entity.
    Tracks ongoing patient dialogues across messaging channels (e.g. WhatsApp).
    """
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_clinic_status", "clinic_id", "status"),
        Index("ix_conversations_clinic_external", "clinic_id", "external_conversation_id"),
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
    channel: Mapped[str] = mapped_column(
        String(50),
        default="whatsapp",
        nullable=False,
        comment="Channel: whatsapp, website, instagram, other",
    )
    external_conversation_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        index=True,
        nullable=True,
        comment="External identifier e.g. WhatsApp conversation/phone number",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="open",
        index=True,
        nullable=False,
        comment="Status: open, human_required, closed",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    clinic: Mapped["Clinic"] = relationship("Clinic", back_populates="conversations")
    lead: Mapped[Optional["Lead"]] = relationship("Lead", back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    appointments: Mapped[List["Appointment"]] = relationship(
        "Appointment",
        back_populates="conversation",
    )


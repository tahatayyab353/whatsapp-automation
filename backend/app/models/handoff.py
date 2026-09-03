import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, utc_now

if TYPE_CHECKING:
    from app.models.clinic import Clinic
    from app.models.conversation import Conversation
    from app.models.lead import Lead
    from app.models.user import User


class Handoff(Base, TimestampMixin):
    """
    Tenant-Scoped Human Handoff & Escalation Entity.
    Tracks conversations escalated from AI to human clinic staff.
    """
    __tablename__ = "handoffs"
    __table_args__ = (
        Index("ix_handoffs_clinic_status", "clinic_id", "status"),
        Index("ix_handoffs_conv_status", "conversation_id", "status"),
        Index("ix_handoffs_clinic_requested_at", "clinic_id", "requested_at"),
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
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    assigned_to_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        index=True,
        nullable=False,
        comment="Status: pending, assigned, resolved, cancelled",
    )
    reason: Mapped[str] = mapped_column(
        String(100),
        default="staff_required",
        nullable=False,
        comment="Reason: customer_requested_human, complex_question, complaint, billing_issue, urgent_request, ai_uncertain, staff_required, other",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Contextual notes or summary of why handoff was triggered",
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    assigned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    clinic: Mapped["Clinic"] = relationship("Clinic")
    conversation: Mapped["Conversation"] = relationship("Conversation")
    lead: Mapped[Optional["Lead"]] = relationship("Lead")
    assigned_to: Mapped[Optional["User"]] = relationship("User")


import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utc_now

if TYPE_CHECKING:
    from app.models.clinic import Clinic
    from app.models.conversation import Conversation


class Message(Base):
    """
    Tenant-Scoped Message Entity.
    Represents an individual message exchanged within a conversation.
    """
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_clinic_created", "clinic_id", "created_at"),
        Index("ix_messages_conv_created", "conversation_id", "created_at"),
        UniqueConstraint("clinic_id", "external_message_id", name="uq_messages_clinic_external_id"),
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
    sender_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Sender: customer, ai, staff, system",
    )
    message_type: Mapped[str] = mapped_column(
        String(50),
        default="text",
        nullable=False,
        comment="Message type: text, image, audio, document, other",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    external_message_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        index=True,
        nullable=True,
        comment="External message identifier e.g. WhatsApp wamid",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        index=True,
        nullable=False,
    )

    # Relationships
    clinic: Mapped["Clinic"] = relationship("Clinic", back_populates="messages")
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")

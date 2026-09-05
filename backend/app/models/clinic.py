from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.membership import ClinicMembership
    from app.models.lead import Lead
    from app.models.conversation import Conversation
    from app.models.message import Message
    from app.models.appointment import Appointment
    from app.models.knowledge import KnowledgeDocument
    from app.models.whatsapp import WhatsAppAccount
    from app.models.calendar import CalendarConnection


class Clinic(Base, TimestampMixin):
    """
    Clinic Tenant Entity.
    Represents the primary tenant container in the multi-tenant architecture.
    """
    __tablename__ = "clinics"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Karachi", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    memberships: Mapped[List["ClinicMembership"]] = relationship(
        "ClinicMembership",
        back_populates="clinic",
        cascade="all, delete-orphan",
    )
    leads: Mapped[List["Lead"]] = relationship(
        "Lead",
        back_populates="clinic",
        cascade="all, delete-orphan",
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation",
        back_populates="clinic",
        cascade="all, delete-orphan",
    )
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="clinic",
        cascade="all, delete-orphan",
    )
    appointments: Mapped[List["Appointment"]] = relationship(
        "Appointment",
        back_populates="clinic",
        cascade="all, delete-orphan",
    )
    knowledge_documents: Mapped[List["KnowledgeDocument"]] = relationship(
        "KnowledgeDocument",
        back_populates="clinic",
        cascade="all, delete-orphan",
    )
    whatsapp_accounts: Mapped[List["WhatsAppAccount"]] = relationship(
        "WhatsAppAccount",
        back_populates="clinic",
        cascade="all, delete-orphan",
    )
    calendar_connections: Mapped[List["CalendarConnection"]] = relationship(
        "CalendarConnection",
        back_populates="clinic",
        cascade="all, delete-orphan",
    )



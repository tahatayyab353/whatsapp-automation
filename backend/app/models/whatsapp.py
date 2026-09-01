import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic


class WhatsAppAccount(Base, TimestampMixin):
    """
    Tenant-Scoped WhatsApp Integration Configuration.
    Represents a clinic's Meta WhatsApp Cloud API phone number and credentials.
    """
    __tablename__ = "whatsapp_accounts"
    __table_args__ = (
        UniqueConstraint("phone_number_id", name="uq_whatsapp_accounts_phone_number_id"),
    )

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    phone_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="E.164 formatted WhatsApp phone number (e.g. +923001234567)",
    )
    phone_number_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        comment="Meta WhatsApp Phone Number ID for webhook routing",
    )
    business_account_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Meta WhatsApp Business Account (WABA) ID",
    )
    display_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Display name configured in Meta WhatsApp Manager",
    )
    access_token: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Encrypted/secure per-clinic Meta Cloud API System User Access Token",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    clinic: Mapped["Clinic"] = relationship("Clinic", back_populates="whatsapp_accounts")

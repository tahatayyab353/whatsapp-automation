import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic


class WhatsAppAccount(Base, TimestampMixin):
    """
    Tenant-Scoped WhatsApp Integration Configuration.
    Note: Access tokens and secrets are stored in secure environment/vault storage, NOT in the database.
    """
    __tablename__ = "whatsapp_accounts"

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
        comment="E.164 formatted WhatsApp phone number",
    )
    phone_number_id: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
        comment="Meta WhatsApp Phone Number ID",
    )
    business_account_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Meta WhatsApp Business Account (WABA) ID",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    clinic: Mapped["Clinic"] = relationship("Clinic", back_populates="whatsapp_accounts")


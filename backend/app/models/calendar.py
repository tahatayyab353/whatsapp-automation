import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic


class CalendarConnection(Base, TimestampMixin):
    """
    Tenant-Scoped External Calendar Integration Entity.
    Stores encrypted OAuth access and refresh credentials, selected calendar identifiers,
    and connection health for Google Calendar and Microsoft Outlook / 365.
    """
    __tablename__ = "calendar_connections"
    __table_args__ = (
        UniqueConstraint("clinic_id", "provider", name="uq_clinic_calendar_provider"),
        Index("ix_calendar_connections_clinic_provider", "clinic_id", "provider"),
        Index("ix_calendar_connections_status", "status"),
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
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Calendar provider: google, microsoft",
    )
    account_identifier: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="External user/account email or ID (e.g. clinic@gmail.com)",
    )
    calendar_identifier: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        default="primary",
        comment="Target calendar identifier in external system (e.g. 'primary' or specific calendar ID)",
    )
    calendar_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Human-readable name of selected calendar",
    )
    encrypted_access_token: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Encrypted OAuth access token",
    )
    encrypted_refresh_token: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Encrypted OAuth refresh token",
    )
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Access token expiration timestamp (UTC)",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="connected",
        nullable=False,
        comment="Status: connected, expired, disconnected, error",
    )
    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Sanitized last synchronization or refresh error description",
    )
    connected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when connection was authorized",
    )

    # Relationships
    clinic: Mapped["Clinic"] = relationship("Clinic", back_populates="calendar_connections")


import uuid
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic
    from app.models.user import User


class ClinicMembership(Base, TimestampMixin):
    """
    Clinic Membership Entity.
    Associates a platform user with a specific clinic tenant under a specific role.
    """
    __tablename__ = "clinic_memberships"
    __table_args__ = (
        UniqueConstraint("clinic_id", "user_id", name="uq_clinic_membership"),
    )

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="staff",
        comment="Role: owner, admin, staff",
    )

    # Relationships
    clinic: Mapped["Clinic"] = relationship("Clinic", back_populates="memberships")
    user: Mapped["User"] = relationship("User", back_populates="memberships")


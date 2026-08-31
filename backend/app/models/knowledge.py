import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic


class KnowledgeDocument(Base, TimestampMixin):
    """
    Tenant-Scoped Knowledge Base Entity.
    Stores clinic-approved FAQs, service catalogs, policies, and pricing information.
    """
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        Index("ix_knowledge_clinic_category", "clinic_id", "category"),
        Index("ix_knowledge_clinic_active", "clinic_id", "is_active"),
    )

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Category: faq, service, pricing, doctor, location, policy, general",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        nullable=False,
    )

    # Relationships
    clinic: Mapped["Clinic"] = relationship("Clinic", back_populates="knowledge_documents")


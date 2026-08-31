import uuid
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import KnowledgeDocument
from app.schemas.knowledge import KnowledgeCreate, KnowledgeUpdate


class KnowledgeService:
    @staticmethod
    def create_document(
        db: Session,
        clinic_id: uuid.UUID,
        payload: KnowledgeCreate,
    ) -> KnowledgeDocument:
        doc = KnowledgeDocument(
            clinic_id=clinic_id,
            title=payload.title,
            content=payload.content,
            category=payload.category,
            is_active=payload.is_active,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def list_documents(
        db: Session,
        clinic_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[KnowledgeDocument], int]:
        stmt = select(KnowledgeDocument).where(KnowledgeDocument.clinic_id == clinic_id)

        if category:
            stmt = stmt.where(KnowledgeDocument.category == category)
        if is_active is not None:
            stmt = stmt.where(KnowledgeDocument.is_active == is_active)
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    KnowledgeDocument.title.ilike(pattern),
                    KnowledgeDocument.content.ilike(pattern),
                )
            )

        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        offset = (page - 1) * page_size
        items = db.scalars(
            stmt.order_by(KnowledgeDocument.created_at.desc()).offset(offset).limit(page_size)
        ).all()

        return list(items), total

    @staticmethod
    def get_document(
        db: Session,
        clinic_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> KnowledgeDocument:
        doc = db.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.clinic_id == clinic_id,
            )
        )
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge document not found.",
            )
        return doc

    @staticmethod
    def update_document(
        db: Session,
        clinic_id: uuid.UUID,
        document_id: uuid.UUID,
        payload: KnowledgeUpdate,
    ) -> KnowledgeDocument:
        doc = KnowledgeService.get_document(db, clinic_id, document_id)
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(doc, field, value)
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def delete_document(
        db: Session,
        clinic_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> None:
        doc = KnowledgeService.get_document(db, clinic_id, document_id)
        db.delete(doc)
        db.commit()


knowledge_service = KnowledgeService()


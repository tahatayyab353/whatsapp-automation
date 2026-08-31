import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import ClinicContext, require_admin, require_staff
from app.db.database import get_db
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.knowledge import (
    KnowledgeCreate,
    KnowledgeDocumentRead,
    KnowledgeUpdate,
)
from app.services.knowledge_service import knowledge_service

router = APIRouter()


@router.post(
    "",
    response_model=KnowledgeDocumentRead,
    summary="Create Knowledge Document",
    description="Adds a clinic FAQ, treatment explanation, or policy document. Permitted for Owner and Admin.",
)
async def create_document(
    payload: KnowledgeCreate,
    clinic_context: ClinicContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> KnowledgeDocumentRead:
    doc = knowledge_service.create_document(db, clinic_context.clinic.id, payload)
    return KnowledgeDocumentRead.model_validate(doc)


@router.get(
    "",
    response_model=PaginatedResponse[KnowledgeDocumentRead],
    summary="List Knowledge Documents",
    description="Retrieves a paginated list of clinic knowledge documents. Permitted for all staff members.",
)
async def list_documents(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    category: Optional[str] = Query(None, description="Filter by category (faq, service, pricing, doctor, location, policy, general)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search document title or content"),
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> PaginatedResponse[KnowledgeDocumentRead]:
    items, total = knowledge_service.list_documents(
        db=db,
        clinic_id=clinic_context.clinic.id,
        page=page,
        page_size=page_size,
        category=category,
        is_active=is_active,
        search=search,
    )
    return PaginatedResponse[KnowledgeDocumentRead](
        items=[KnowledgeDocumentRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/{document_id}",
    response_model=KnowledgeDocumentRead,
    summary="Get Knowledge Document Details",
    description="Fetches a specific knowledge document by ID belonging to the active clinic.",
)
async def get_document(
    document_id: uuid.UUID,
    clinic_context: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> KnowledgeDocumentRead:
    doc = knowledge_service.get_document(db, clinic_context.clinic.id, document_id)
    return KnowledgeDocumentRead.model_validate(doc)


@router.patch(
    "/{document_id}",
    response_model=KnowledgeDocumentRead,
    summary="Update Knowledge Document",
    description="Updates document title, content, category, or active status. Permitted for Owner and Admin.",
)
async def update_document(
    document_id: uuid.UUID,
    payload: KnowledgeUpdate,
    clinic_context: ClinicContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> KnowledgeDocumentRead:
    updated = knowledge_service.update_document(
        db=db,
        clinic_id=clinic_context.clinic.id,
        document_id=document_id,
        payload=payload,
    )
    return KnowledgeDocumentRead.model_validate(updated)


@router.delete(
    "/{document_id}",
    response_model=MessageResponse,
    summary="Delete Knowledge Document",
    description="Deletes a knowledge document from the active clinic. Permitted for Owner and Admin.",
)
async def delete_document(
    document_id: uuid.UUID,
    clinic_context: ClinicContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    knowledge_service.delete_document(
        db=db,
        clinic_id=clinic_context.clinic.id,
        document_id=document_id,
    )
    return MessageResponse(message="Knowledge document deleted successfully.")


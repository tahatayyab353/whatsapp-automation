import uuid
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Conversation, Lead
from app.schemas.conversation import ConversationCreate, ConversationUpdate


class ConversationService:
    @staticmethod
    def create_conversation(
        db: Session,
        clinic_id: uuid.UUID,
        payload: ConversationCreate,
    ) -> Conversation:
        if payload.lead_id:
            lead = db.scalar(
                select(Lead).where(
                    Lead.id == payload.lead_id,
                    Lead.clinic_id == clinic_id,
                )
            )
            if not lead:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Lead not found for this clinic.",
                )

        conversation = Conversation(
            clinic_id=clinic_id,
            lead_id=payload.lead_id,
            channel=payload.channel,
            external_conversation_id=payload.external_conversation_id,
            status="open",
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation

    @staticmethod
    def list_conversations(
        db: Session,
        clinic_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        conv_status: Optional[str] = None,
        channel: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[Conversation], int]:
        stmt = select(Conversation).where(Conversation.clinic_id == clinic_id)

        if conv_status:
            stmt = stmt.where(Conversation.status == conv_status)
        if channel:
            stmt = stmt.where(Conversation.channel == channel)
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(Conversation.external_conversation_id.ilike(pattern))

        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        offset = (page - 1) * page_size
        items = db.scalars(
            stmt.order_by(Conversation.created_at.desc()).offset(offset).limit(page_size)
        ).all()

        return list(items), total

    @staticmethod
    def get_conversation(
        db: Session,
        clinic_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> Conversation:
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.clinic_id == clinic_id,
            )
        )
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )
        return conversation

    @staticmethod
    def update_conversation(
        db: Session,
        clinic_id: uuid.UUID,
        conversation_id: uuid.UUID,
        payload: ConversationUpdate,
    ) -> Conversation:
        conversation = ConversationService.get_conversation(db, clinic_id, conversation_id)
        conversation.status = payload.status
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation


conversation_service = ConversationService()


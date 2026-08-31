import uuid
from datetime import datetime, timezone
from typing import List, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Conversation, Message
from app.schemas.message import MessageCreate


class MessageService:
    @staticmethod
    def create_message(
        db: Session,
        clinic_id: uuid.UUID,
        conversation_id: uuid.UUID,
        payload: MessageCreate,
    ) -> Message:
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

        now = datetime.now(timezone.utc)
        message = Message(
            clinic_id=clinic_id,
            conversation_id=conversation_id,
            sender_type=payload.sender_type,
            message_type=payload.message_type,
            content=payload.content,
            external_message_id=payload.external_message_id,
            created_at=now,
        )
        conversation.last_message_at = now

        db.add(message)
        db.add(conversation)
        db.commit()
        db.refresh(message)
        return message

    @staticmethod
    def list_messages(
        db: Session,
        clinic_id: uuid.UUID,
        conversation_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Message], int]:
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

        stmt = select(Message).where(
            Message.conversation_id == conversation_id,
            Message.clinic_id == clinic_id,
        )
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        offset = (page - 1) * page_size
        items = db.scalars(
            stmt.order_by(Message.created_at.asc()).offset(offset).limit(page_size)
        ).all()

        return list(items), total


message_service = MessageService()


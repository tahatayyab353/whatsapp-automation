import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, NotFoundException
from app.core.logging import logger
from app.integrations.whatsapp.client import WhatsAppClient
from app.models import Conversation, Handoff, Lead, Message, WhatsAppAccount
from app.models.base import utc_now


class HandoffService:
    """
    Manages human escalation and handoff lifecycles for conversations:
    request, assign to staff, resolve, cancel, and staff reply transmission.
    """

    @classmethod
    def request_handoff(
        cls,
        db: Session,
        clinic_id: uuid.UUID,
        conversation_id: uuid.UUID,
        reason: str = "staff_required",
        notes: Optional[str] = None,
    ) -> Handoff:
        """
        Escalates a conversation to human staff. Reuses existing pending/assigned handoff if active.
        """
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.clinic_id == clinic_id,
            )
        )
        if not conversation:
            raise NotFoundException("Conversation not found.")

        # Check for existing active handoff to prevent duplicates
        active_handoff = db.scalar(
            select(Handoff).where(
                Handoff.clinic_id == clinic_id,
                Handoff.conversation_id == conversation_id,
                Handoff.status.in_(["pending", "assigned"]),
            )
        )
        if active_handoff:
            logger.info("Active handoff already exists for conversation %s", conversation_id)
            return active_handoff

        handoff = Handoff(
            clinic_id=clinic_id,
            conversation_id=conversation.id,
            lead_id=conversation.lead_id,
            status="pending",
            reason=reason,
            notes=notes,
            requested_at=utc_now(),
        )
        conversation.status = "human_required"
        db.add(handoff)
        db.add(conversation)
        db.commit()
        db.refresh(handoff)
        logger.info("Created new human handoff | handoff_id=%s | reason=%s", handoff.id, reason)
        return handoff

    @classmethod
    def assign_handoff(
        cls,
        db: Session,
        clinic_id: uuid.UUID,
        handoff_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Handoff:
        """
        Claims or assigns an active handoff to a staff user.
        """
        handoff = db.scalar(
            select(Handoff).where(
                Handoff.id == handoff_id,
                Handoff.clinic_id == clinic_id,
            )
        )
        if not handoff:
            raise NotFoundException("Handoff not found.")

        if handoff.status in ["resolved", "cancelled"]:
            raise BadRequestException(f"Cannot assign handoff with status '{handoff.status}'.")

        handoff.status = "assigned"
        handoff.assigned_to_user_id = user_id
        handoff.assigned_at = utc_now()

        conversation = db.scalar(
            select(Conversation).where(
                Conversation.id == handoff.conversation_id,
                Conversation.clinic_id == clinic_id,
            )
        )
        if conversation:
            conversation.status = "human_required"
            db.add(conversation)

        db.add(handoff)
        db.commit()
        db.refresh(handoff)
        logger.info("Assigned handoff %s to user %s", handoff_id, user_id)
        return handoff

    @classmethod
    def resolve_handoff(
        cls,
        db: Session,
        clinic_id: uuid.UUID,
        handoff_id: uuid.UUID,
        notes: Optional[str] = None,
    ) -> Handoff:
        """
        Resolves a handoff and resets conversation status so AI can respond to future inquiries.
        """
        handoff = db.scalar(
            select(Handoff).where(
                Handoff.id == handoff_id,
                Handoff.clinic_id == clinic_id,
            )
        )
        if not handoff:
            raise NotFoundException("Handoff not found.")

        if handoff.status in ["resolved", "cancelled"]:
            raise BadRequestException(f"Handoff is already {handoff.status}.")

        handoff.status = "resolved"
        handoff.resolved_at = utc_now()
        if notes:
            handoff.notes = f"{handoff.notes}\n[Resolution] {notes}" if handoff.notes else f"[Resolution] {notes}"

        conversation = db.scalar(
            select(Conversation).where(
                Conversation.id == handoff.conversation_id,
                Conversation.clinic_id == clinic_id,
            )
        )
        if conversation:
            conversation.status = "open"
            db.add(conversation)

        db.add(handoff)
        db.commit()
        db.refresh(handoff)
        logger.info("Resolved handoff %s", handoff_id)
        return handoff

    @classmethod
    def cancel_handoff(
        cls,
        db: Session,
        clinic_id: uuid.UUID,
        handoff_id: uuid.UUID,
        notes: Optional[str] = None,
    ) -> Handoff:
        """
        Cancels a handoff and returns conversation to open status.
        """
        handoff = db.scalar(
            select(Handoff).where(
                Handoff.id == handoff_id,
                Handoff.clinic_id == clinic_id,
            )
        )
        if not handoff:
            raise NotFoundException("Handoff not found.")

        if handoff.status in ["resolved", "cancelled"]:
            raise BadRequestException(f"Handoff is already {handoff.status}.")

        handoff.status = "cancelled"
        handoff.resolved_at = utc_now()
        if notes:
            handoff.notes = f"{handoff.notes}\n[Cancelled] {notes}" if handoff.notes else f"[Cancelled] {notes}"

        conversation = db.scalar(
            select(Conversation).where(
                Conversation.id == handoff.conversation_id,
                Conversation.clinic_id == clinic_id,
            )
        )
        if conversation:
            conversation.status = "open"
            db.add(conversation)

        db.add(handoff)
        db.commit()
        db.refresh(handoff)
        logger.info("Cancelled handoff %s", handoff_id)
        return handoff

    @classmethod
    def get_handoff(
        cls,
        db: Session,
        clinic_id: uuid.UUID,
        handoff_id: uuid.UUID,
    ) -> Handoff:
        handoff = db.scalar(
            select(Handoff).where(
                Handoff.id == handoff_id,
                Handoff.clinic_id == clinic_id,
            )
        )
        if not handoff:
            raise NotFoundException("Handoff not found.")
        return handoff

    @classmethod
    def list_handoffs(
        cls,
        db: Session,
        clinic_id: uuid.UUID,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Handoff]:
        stmt = select(Handoff).where(Handoff.clinic_id == clinic_id)
        if status:
            stmt = stmt.where(Handoff.status == status)
        stmt = stmt.order_by(Handoff.requested_at.desc()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    @classmethod
    def is_human_active(
        cls,
        db: Session,
        clinic_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> bool:
        """
        Checks whether a conversation is under human staff control or awaiting human pickup.
        """
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.clinic_id == clinic_id,
            )
        )
        if not conversation:
            return False

        if conversation.status == "human_required":
            return True

        active_handoff = db.scalar(
            select(Handoff).where(
                Handoff.clinic_id == clinic_id,
                Handoff.conversation_id == conversation_id,
                Handoff.status.in_(["pending", "assigned"]),
            )
        )
        return active_handoff is not None

    @classmethod
    async def send_staff_message(
        cls,
        db: Session,
        clinic_id: uuid.UUID,
        conversation_id: uuid.UUID,
        staff_user_id: uuid.UUID,
        content: str,
    ) -> Message:
        """
        Sends an authenticated staff reply to a customer via Meta WhatsApp Cloud API
        and records the message with sender_type='staff'.
        """
        # 1. Verify Conversation & Clinic
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.clinic_id == clinic_id,
            )
        )
        if not conversation:
            raise NotFoundException("Conversation not found.")

        # 2. Resolve Customer Phone
        lead = db.scalar(
            select(Lead).where(
                Lead.id == conversation.lead_id,
                Lead.clinic_id == clinic_id,
            )
        )
        if not lead or not lead.phone:
            raise BadRequestException("Lead phone number not found for conversation.")

        # 3. Resolve active WhatsApp credentials
        account = db.scalar(
            select(WhatsAppAccount).where(
                WhatsAppAccount.clinic_id == clinic_id,
                WhatsAppAccount.is_active == True,  # noqa: E712
            )
        )
        if not account:
            raise BadRequestException("No active WhatsApp account configured for clinic.")

        # 4. Outbound Meta send
        whatsapp_client = WhatsAppClient(
            access_token=account.access_token,
            phone_number_id=account.phone_number_id,
        )
        outbound_res = await whatsapp_client.send_text_message(
            recipient_phone=lead.phone,
            message=content,
        )
        meta_id = (
            outbound_res.messages[0].id
            if outbound_res and outbound_res.messages
            else f"outbound-staff-{uuid.uuid4()}"
        )

        # 5. Persist staff message
        message = Message(
            clinic_id=clinic_id,
            conversation_id=conversation.id,
            sender_type="staff",
            message_type="text",
            content=content,
            external_message_id=meta_id,
            created_at=utc_now(),
        )
        conversation.last_message_at = utc_now()
        db.add(message)
        db.add(conversation)
        db.commit()
        db.refresh(message)
        logger.info("Persisted staff reply for conversation %s", conversation_id)
        return message


handoff_service = HandoffService()


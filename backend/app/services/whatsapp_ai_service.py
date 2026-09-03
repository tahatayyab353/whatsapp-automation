import re
import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.receptionist import receptionist_service
from app.core.logging import logger
from app.integrations.whatsapp.client import WhatsAppClient
from app.integrations.whatsapp.exceptions import WhatsAppIntegrationError
from app.models import Clinic, Conversation, Handoff, Message, WhatsAppAccount
from app.models.base import utc_now
from app.services.handoff_service import handoff_service

EXPLICIT_HUMAN_PATTERNS = [
    r"\b(talk|speak)\s+(to|with)\s+(a\s+)?(human|person|someone|receptionist|staff|doctor|agent|manager)\b",
    r"\bconnect\s+me\s+(to|with)\s+(the\s+)?(receptionist|staff|human|person|doctor|team)\b",
    r"\b(call|contact)\s+me\b",
    r"\bdon'?t\s+want\s+to\s+talk\s+to\s+a\s+bot\b",
    r"\bhuman\s+please\b",
]

COMPLAINT_PATTERNS = [
    r"\b(make|file|have)\s+(a\s+)?complaint\b",
    r"\bunhappy\s+with\s+(this|the|your)\s+service\b",
    r"\bterrible\s+service\b",
    r"\bmessed\s+up\s+(my\s+)?appointment\b",
    r"\bworst\s+experience\b",
]


class WhatsAppAIService:
    """
    Orchestrates the AI Receptionist response pipeline for incoming customer WhatsApp messages:
    1. Enforces AI stop condition when human staff is active or requested.
    2. Detects explicit human requests, complaints, and escalations.
    3. Generates grounded reply via ReceptionistService (Gemini primary -> Groq fallback).
    4. Applies race condition protection before dispatching.
    5. Sends the AI reply via Meta WhatsApp Cloud API.
    6. Persists the AI response message and updates conversation state.
    """

    @classmethod
    def _detect_escalation_intent(cls, message_text: str) -> Optional[str]:
        cleaned = message_text.lower()
        for pattern in COMPLAINT_PATTERNS:
            if re.search(pattern, cleaned):
                return "complaint"
        for pattern in EXPLICIT_HUMAN_PATTERNS:
            if re.search(pattern, cleaned):
                return "customer_requested_human"
        return None

    @classmethod
    async def process_and_reply_customer_message(
        cls,
        db: Session,
        clinic_id: uuid.UUID,
        conversation_id: uuid.UUID,
        customer_message: str,
        customer_phone: str,
    ) -> Optional[Message]:
        # 1. Retrieve Clinic and Conversation context
        clinic = db.scalar(select(Clinic).where(Clinic.id == clinic_id))
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.clinic_id == clinic_id,
            )
        )
        if not clinic or not conversation:
            logger.error("Clinic or Conversation not found during AI processing.")
            return None

        # 2. AI Stop Condition: If human is already active/assigned, do not invoke AI
        active_assigned_handoff = db.scalar(
            select(Handoff).where(
                Handoff.clinic_id == clinic_id,
                Handoff.conversation_id == conversation.id,
                Handoff.status == "assigned",
            )
        )
        if active_assigned_handoff:
            logger.info("Conversation %s is actively handled by staff, skipping AI reply.", conversation.id)
            return None

        # 3. Escalation Check: Check if message explicitly requests human or files complaint
        escalation_reason = cls._detect_escalation_intent(customer_message)
        if escalation_reason:
            logger.info("Detected human handoff trigger (%s) for conversation %s", escalation_reason, conversation.id)
            handoff_service.request_handoff(
                db=db,
                clinic_id=clinic_id,
                conversation_id=conversation.id,
                reason=escalation_reason,
                notes=f"Customer message triggered escalation: {customer_message[:150]}",
            )

        # 4. Generate grounded AI response (Gemini -> Groq fallback)
        try:
            logger.info("AI receptionist generation started for clinic.")
            ai_response = await receptionist_service.generate_receptionist_response(
                db=db,
                clinic=clinic,
                conversation=conversation,
                customer_message_text=customer_message,
            )
        except Exception as exc:
            logger.error("AI receptionist generation failed for conversation: %s", str(exc))
            # Critical Rule: Never invent fallback replies or send dummy messages
            return None

        if not ai_response or not ai_response.content:
            logger.warning("Empty AI response received, skipping outbound reply.")
            return None

        # 5. Check if AI response itself indicates handoff / uncertainty
        if "connect you with" in ai_response.content.lower() or "front-desk staff" in ai_response.content.lower() or "our team" in ai_response.content.lower():
            if not escalation_reason:
                handoff_service.request_handoff(
                    db=db,
                    clinic_id=clinic_id,
                    conversation_id=conversation.id,
                    reason="ai_uncertain",
                    notes="AI referred customer to front-desk staff",
                )

        # 6. Race Condition Protection: Re-check if staff claimed conversation while AI was generating
        staff_claimed = db.scalar(
            select(Handoff).where(
                Handoff.clinic_id == clinic_id,
                Handoff.conversation_id == conversation.id,
                Handoff.status == "assigned",
            )
        )
        if staff_claimed and staff_claimed.assigned_to_user_id is not None:
            logger.info("Staff claimed conversation %s during AI generation, discarding AI response.", conversation.id)
            return None

        # 7. Retrieve clinic-specific WhatsApp account credentials
        account = db.scalar(
            select(WhatsAppAccount).where(
                WhatsAppAccount.clinic_id == clinic_id,
                WhatsAppAccount.is_active == True,  # noqa: E712
            )
        )
        if not account:
            logger.error("No active WhatsApp account configured for clinic.")
            return None

        # 8. Dispatch outbound reply to Meta WhatsApp Cloud API
        whatsapp_client = WhatsAppClient(
            access_token=account.access_token,
            phone_number_id=account.phone_number_id,
        )

        try:
            logger.info("Dispatching outbound AI reply via Meta WhatsApp Cloud API.")
            outbound_res = await whatsapp_client.send_text_message(
                recipient_phone=customer_phone,
                message=ai_response.content,
            )
        except WhatsAppIntegrationError as exc:
            logger.error("Meta WhatsApp Cloud API outbound send failed: %s", str(exc))
            return None
        except Exception as exc:
            logger.error("Unexpected error sending WhatsApp outbound message: %s", str(exc))
            return None

        meta_message_id = (
            outbound_res.messages[0].id
            if outbound_res and outbound_res.messages
            else f"outbound-{uuid.uuid4()}"
        )

        # 9. Persist AI message in the database in a discrete transaction
        try:
            ai_message = Message(
                clinic_id=clinic_id,
                conversation_id=conversation.id,
                sender_type="ai",
                message_type="text",
                content=ai_response.content,
                external_message_id=meta_message_id,
                created_at=utc_now(),
            )
            conversation.last_message_at = utc_now()
            db.add(ai_message)
            db.add(conversation)
            db.commit()
            db.refresh(ai_message)
            logger.info("Persisted outbound AI WhatsApp message.")
            return ai_message
        except Exception as exc:
            db.rollback()
            logger.error("Failed to persist outbound AI message: %s", str(exc))
            return None


whatsapp_ai_service = WhatsAppAIService()

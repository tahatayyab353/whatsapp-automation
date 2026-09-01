import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.receptionist import receptionist_service
from app.core.logging import logger
from app.integrations.whatsapp.client import WhatsAppClient
from app.integrations.whatsapp.exceptions import WhatsAppIntegrationError
from app.models import Clinic, Conversation, Message, WhatsAppAccount
from app.models.base import utc_now


class WhatsAppAIService:
    """
    Orchestrates the AI Receptionist response pipeline for incoming customer WhatsApp messages:
    1. Generates grounded reply via ReceptionistService (Gemini primary -> Groq fallback).
    2. Sends the AI reply via Meta WhatsApp Cloud API.
    3. Persists the AI response message and updates conversation state.
    """

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

        # 2. Generate grounded AI response (Gemini -> Groq fallback)
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

        # 3. Retrieve clinic-specific WhatsApp account credentials
        account = db.scalar(
            select(WhatsAppAccount).where(
                WhatsAppAccount.clinic_id == clinic_id,
                WhatsAppAccount.is_active == True,  # noqa: E712
            )
        )
        if not account:
            logger.error("No active WhatsApp account configured for clinic.")
            return None

        # 4. Dispatch outbound reply to Meta WhatsApp Cloud API
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

        # 5. Persist AI message in the database in a discrete transaction
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


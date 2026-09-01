from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models import Conversation, Lead, Message
from app.schemas.whatsapp_webhook import WebhookPayload
from app.services.whatsapp_ai_service import whatsapp_ai_service
from app.services.whatsapp_service import whatsapp_service


class WhatsAppWebhookService:
    """
    Handles incoming Meta WhatsApp Cloud API events:
    Tenant routing, message deduplication, Lead resolution/creation,
    Conversation resolution/creation, Message persistence, and AI response orchestration.
    """

    @staticmethod
    def _normalize_phone(raw_phone: str) -> str:
        """
        Normalizes a WhatsApp phone number to standard E.164 string format.
        """
        cleaned = raw_phone.strip()
        if cleaned.startswith("+"):
            return cleaned
        return f"+{cleaned}"

    @staticmethod
    def _parse_timestamp(timestamp_str: Optional[str]) -> datetime:
        """
        Parses Meta Unix epoch timestamp string into a timezone-aware UTC datetime.
        """
        if not timestamp_str:
            return datetime.now(timezone.utc)
        try:
            epoch = int(timestamp_str)
            return datetime.fromtimestamp(epoch, tz=timezone.utc)
        except (ValueError, TypeError, OverflowError):
            return datetime.now(timezone.utc)

    @classmethod
    async def process_webhook_payload(
        cls,
        db: Session,
        payload: WebhookPayload,
    ) -> Dict[str, str]:
        if payload.object != "whatsapp_business_account":
            logger.info("Ignoring non-WhatsApp webhook event object: %s", payload.object)
            return {"status": "ok"}

        # Store incoming messages to process with AI after database ingestion
        pending_ai_replies: List[Tuple[Any, Any, str, str]] = []

        for entry in payload.entry:
            for change in entry.changes:
                if change.field != "messages" or not change.value:
                    continue

                value = change.value
                if not value.metadata or not value.metadata.phone_number_id:
                    continue

                phone_number_id = value.metadata.phone_number_id

                # 1. Tenant Routing: Resolve active WhatsAppAccount and Clinic
                account = whatsapp_service.get_account_by_phone_number_id(db, phone_number_id)
                if not account or not account.is_active:
                    logger.info("Ignoring webhook for unconfigured or inactive WhatsApp account.")
                    continue

                clinic_id = account.clinic_id

                # 2. Check for incoming messages
                if not value.messages:
                    continue

                # Build lookup for contact profile names
                contact_names: Dict[str, str] = {}
                if value.contacts:
                    for contact in value.contacts:
                        if contact.wa_id and contact.profile and contact.profile.name:
                            contact_names[contact.wa_id] = contact.profile.name.strip()

                # Process each incoming message inside transaction
                for msg in value.messages:
                    # Only persist supported text messages for AI processing
                    if msg.type != "text" or not msg.text or not msg.text.body:
                        logger.info("Skipping non-text or empty WhatsApp message type: %s", msg.type)
                        continue

                    msg_id = msg.id
                    customer_raw_phone = msg.from_
                    customer_phone = cls._normalize_phone(customer_raw_phone)
                    text_body = msg.text.body
                    msg_time = cls._parse_timestamp(msg.timestamp)

                    try:
                        # 3. Idempotency Check: Prevent duplicate message ingestion
                        existing_msg = db.scalar(
                            select(Message).where(
                                Message.clinic_id == clinic_id,
                                Message.external_message_id == msg_id,
                            )
                        )
                        if existing_msg:
                            logger.info("Duplicate WhatsApp message received, skipping ingestion.")
                            continue

                        # 4. Lead Resolution: Find existing lead for this clinic or create new
                        lead = db.scalar(
                            select(Lead).where(
                                Lead.clinic_id == clinic_id,
                                or_(
                                    Lead.phone == customer_phone,
                                    Lead.phone == customer_raw_phone,
                                ),
                            )
                        )
                        if not lead:
                            profile_name = (
                                contact_names.get(customer_raw_phone)
                                or contact_names.get(customer_phone)
                                or customer_phone
                            )
                            lead = Lead(
                                clinic_id=clinic_id,
                                full_name=profile_name,
                                phone=customer_phone,
                                source="whatsapp",
                                status="new",
                            )
                            db.add(lead)
                            db.flush()
                            logger.info("Created new patient lead for clinic.")
                        else:
                            logger.info("Reused existing patient lead for clinic.")

                        # 5. Conversation Resolution: Find open conversation or start new
                        conversation = db.scalar(
                            select(Conversation)
                            .where(
                                Conversation.clinic_id == clinic_id,
                                Conversation.lead_id == lead.id,
                                Conversation.channel == "whatsapp",
                                Conversation.status.in_(["open", "human_required"]),
                            )
                            .order_by(Conversation.created_at.desc())
                        )
                        if not conversation:
                            conversation = Conversation(
                                clinic_id=clinic_id,
                                lead_id=lead.id,
                                channel="whatsapp",
                                external_conversation_id=customer_phone,
                                status="open",
                                started_at=msg_time,
                                last_message_at=msg_time,
                            )
                            db.add(conversation)
                            db.flush()
                            logger.info("Created new conversation thread.")
                        else:
                            conversation.last_message_at = msg_time
                            db.add(conversation)
                            logger.info("Reused active conversation thread.")

                        # 6. Message Persistence
                        new_message = Message(
                            clinic_id=clinic_id,
                            conversation_id=conversation.id,
                            sender_type="customer",
                            message_type="text",
                            content=text_body,
                            external_message_id=msg_id,
                            created_at=msg_time,
                        )
                        db.add(new_message)
                        db.commit()
                        logger.info("Persisted customer WhatsApp message.")

                        # Queue for AI response generation after database commit
                        pending_ai_replies.append(
                            (clinic_id, conversation.id, text_body, customer_phone)
                        )

                    except Exception as exc:
                        db.rollback()
                        logger.error("Error processing incoming WhatsApp message: %s", str(exc))
                        continue

        # 7. Execute AI Receptionist response pipeline for ingested messages
        for clinic_id, conversation_id, text_body, customer_phone in pending_ai_replies:
            try:
                await whatsapp_ai_service.process_and_reply_customer_message(
                    db=db,
                    clinic_id=clinic_id,
                    conversation_id=conversation_id,
                    customer_message=text_body,
                    customer_phone=customer_phone,
                )
            except Exception as exc:
                logger.error("Error in AI receptionist response pipeline: %s", str(exc))

        return {"status": "ok"}


whatsapp_webhook_service = WhatsAppWebhookService()

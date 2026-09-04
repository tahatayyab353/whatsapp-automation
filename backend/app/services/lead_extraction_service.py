import json
import re
import uuid
from typing import List, Optional
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.exceptions import AIAuthenticationError
from app.ai.factory import get_fallback_provider, get_primary_provider
from app.core.logging import logger
from app.models import Conversation, Lead, Message
from app.schemas.lead_extraction import ExtractedLeadData


class LeadExtractionService:
    """
    Extracts structured lead metadata and automatic lead qualification from conversation history.
    Uses Primary AI (Gemini) with automatic fallback to Groq.
    Updates existing Lead records non-destructively without overwriting canonical phone or existing data with null.
    """

    EXTRACTION_SYSTEM_PROMPT = """You are a specialized Medical CRM Data Extraction Assistant.
Your task is to analyze the recent conversation between a customer and clinic staff/receptionist, and extract structured lead details and qualification.

CRITICAL INSTRUCTIONS:
1. ONLY extract information that is explicitly stated or clearly implied by the customer.
2. DO NOT hallucinate, guess, or invent full names, emails, phone numbers, or services.
3. If a field is NOT provided by the customer, set its value to null.
4. Output MUST be a single valid JSON object strictly adhering to the specified schema:
{
  "full_name": string or null,
  "email": string or null,
  "phone": string or null,
  "service_interest": string or null,
  "intent": "low" | "medium" | "high" | null,
  "urgency": "low" | "medium" | "high" | null,
  "notes": string or null,
  "status": "new" | "contacted" | "qualified" | "appointment_requested" | "booked" | "converted" | "lost" | null
}
5. Qualification Rules:
   - intent: "high" if customer asks to book/schedule, gives specific availability, or asks for address to visit immediately.
   - intent: "medium" if customer asks for specific service pricing, treatment details, or doctor qualifications.
   - intent: "low" if customer only said hello/general greetings.
   - status: "appointment_requested" if customer wants an appointment scheduled.
   - status: "qualified" if customer specified an interested procedure/service.
   - status: "contacted" if conversation is preliminary.
"""

    @classmethod
    def _parse_and_validate_json(cls, raw_content: str) -> Optional[ExtractedLeadData]:
        if not raw_content:
            return None

        # Clean markdown fences if present
        text = raw_content.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # Regex fallback to find JSON block
        json_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if json_match:
            text = json_match.group(1)

        try:
            parsed = json.loads(text)
            return ExtractedLeadData.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("Failed to parse or validate AI lead extraction JSON: %s", str(exc))
            return None

    @classmethod
    async def extract_lead_from_conversation(
        cls,
        db: Session,
        clinic_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> Optional[ExtractedLeadData]:
        """
        Analyzes conversation history, extracts lead metadata via AI, and updates the CRM Lead record non-destructively.
        """
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.clinic_id == clinic_id,
            )
        )
        if not conversation or not conversation.lead_id:
            logger.warning("Conversation %s not found or has no associated lead.", conversation_id)
            return None

        lead = db.scalar(
            select(Lead).where(
                Lead.id == conversation.lead_id,
                Lead.clinic_id == clinic_id,
            )
        )
        if not lead:
            logger.warning("Lead %s not found for clinic %s.", conversation.lead_id, clinic_id)
            return None

        # Fetch recent messages chronologically (limit 15)
        recent_messages: List[Message] = list(
            db.scalars(
                select(Message)
                .where(
                    Message.conversation_id == conversation.id,
                    Message.clinic_id == clinic_id,
                )
                .order_by(Message.created_at.desc())
                .limit(15)
            ).all()
        )
        recent_messages.reverse()

        if not recent_messages:
            return None

        transcript_lines = []
        for msg in recent_messages:
            role_label = "Customer" if msg.sender_type == "customer" else "Receptionist"
            transcript_lines.append(f"{role_label}: {msg.content}")
        transcript = "\n".join(transcript_lines)

        user_prompt = f"Analyze this conversation transcript and extract lead details:\n\n{transcript}"
        messages = [
            {"role": "system", "content": cls.EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        extracted: Optional[ExtractedLeadData] = None

        # 1. Primary AI Provider (Gemini)
        primary = get_primary_provider()
        try:
            logger.info("Initiating AI lead extraction via primary provider.")
            resp = await primary.generate(messages=messages, temperature=0.1, max_tokens=500)
            extracted = cls._parse_and_validate_json(resp.content)
        except AIAuthenticationError:
            logger.error("Primary AI authentication failure during lead extraction.")
            return None
        except Exception as exc:
            logger.warning("Primary AI failed during lead extraction: %s. Attempting fallback.", str(exc))

        # 2. Fallback AI Provider (Groq)
        if not extracted:
            fallback = get_fallback_provider()
            try:
                logger.info("Initiating AI lead extraction via fallback provider.")
                resp = await fallback.generate(messages=messages, temperature=0.1, max_tokens=500)
                extracted = cls._parse_and_validate_json(resp.content)
            except Exception as exc:
                logger.error("Fallback AI provider also failed during lead extraction: %s", str(exc))
                return None

        if not extracted:
            return None

        # 3. Non-destructive CRM Lead updates
        updated = False

        # Name update (only if lead has default phone or placeholder name)
        if extracted.full_name and extracted.full_name.strip():
            candidate = extracted.full_name.strip()
            # If current full_name is None, empty, or equals phone number
            if not lead.full_name or lead.full_name == lead.phone or lead.full_name == "+923009998877":
                lead.full_name = candidate
                updated = True
            elif lead.full_name and lead.full_name.startswith("+"):
                lead.full_name = candidate
                updated = True

        # Email update
        if extracted.email and extracted.email.strip():
            candidate_email = extracted.email.strip().lower()
            if not lead.email:
                lead.email = candidate_email
                updated = True

        # Service Interest update
        if extracted.service_interest and extracted.service_interest.strip():
            lead.service_interest = extracted.service_interest.strip()
            updated = True

        # Status & Qualification transitions (never downgrade terminal/advanced states)
        terminal_statuses = {"appointment_requested", "booked", "converted", "lost"}
        if lead.status not in terminal_statuses:
            if extracted.status in ["appointment_requested", "qualified", "contacted"]:
                lead.status = extracted.status
                updated = True
            elif extracted.service_interest:
                lead.status = "qualified"
                updated = True
            elif lead.status == "new":
                lead.status = "contacted"
                updated = True

        # Append structured notes if provided
        notes_parts = []
        if extracted.intent:
            notes_parts.append(f"Intent: {extracted.intent}")
        if extracted.urgency:
            notes_parts.append(f"Urgency: {extracted.urgency}")
        if extracted.notes:
            notes_parts.append(f"Notes: {extracted.notes}")

        if notes_parts:
            new_notes = " | ".join(notes_parts)
            lead.notes = f"{lead.notes}\n[AI Extraction] {new_notes}" if lead.notes else f"[AI Extraction] {new_notes}"
            updated = True

        if updated:
            db.add(lead)
            db.commit()
            db.refresh(lead)
            logger.info("Updated CRM lead %s with extracted AI details.", lead.id)

        # 4. If customer requested an appointment, idempotently record an appointment request
        if extracted.status == "appointment_requested":
            try:
                from app.services.appointment_service import appointment_service
                from datetime import timedelta
                from app.models.base import utc_now
                # Default request slot: tomorrow at current time + 1 day
                target_sched = utc_now() + timedelta(days=1)
                title_desc = f"{extracted.service_interest or 'Consultation'} Request"
                appointment_service.create_appointment_request_from_ai(
                    db=db,
                    clinic_id=clinic_id,
                    lead_id=lead.id,
                    conversation_id=conversation.id,
                    scheduled_at=target_sched,
                    title=title_desc,
                    notes=extracted.notes or "AI detected appointment request from conversation transcript.",
                )
            except Exception as exc:
                logger.warning("Failed to auto-create appointment request from AI extraction: %s", str(exc))

        return extracted


lead_extraction_service = LeadExtractionService()

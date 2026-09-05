import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.integrations.whatsapp.client import WhatsAppClient
from app.integrations.whatsapp.exceptions import (
    WhatsAppAPIError,
    WhatsAppAuthenticationError,
    WhatsAppIntegrationError,
    WhatsAppNetworkError,
    WhatsAppRateLimitError,
)
from app.models import Appointment, AppointmentReminder, Clinic, Lead, WhatsAppAccount
from app.models.base import utc_now
from app.services.reminder_templates import build_reminder_message

ELIGIBLE_STATUSES = {"requested", "confirmed"}
TERMINAL_OR_CLOSED_STATUSES = {"cancelled", "completed", "no_show"}


class ReminderService:
    """
    Core notification and appointment reminder service:
    1. Idempotently creates 24h and 2h reminder schedules for appointments.
    2. Atomically claims due reminders to prevent double-send race conditions.
    3. Re-checks eligibility and dispatches WhatsApp messages.
    4. Handles bounded retries, permanent failure detection, cancellation, and rescheduling.
    """

    @classmethod
    def schedule_appointment_reminders(
        cls,
        db: Session,
        appointment: Appointment,
    ) -> List[AppointmentReminder]:
        """
        Idempotently creates 24h and 2h reminder records for eligible appointments.
        """
        if appointment.status not in ELIGIBLE_STATUSES:
            logger.info("Appointment %s status '%s' is not eligible for reminders", appointment.id, appointment.status)
            return []

        scheduled_at = appointment.scheduled_at
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)

        time_24h = scheduled_at - timedelta(hours=24)
        time_2h = scheduled_at - timedelta(hours=2)

        created_or_updated: List[AppointmentReminder] = []

        for reminder_type, target_time in [
            ("APPOINTMENT_24H", time_24h),
            ("APPOINTMENT_2H", time_2h),
        ]:
            existing = db.scalar(
                select(AppointmentReminder).where(
                    AppointmentReminder.appointment_id == appointment.id,
                    AppointmentReminder.reminder_type == reminder_type,
                )
            )

            if existing:
                # If already sent, do not modify
                if existing.status == "sent":
                    created_or_updated.append(existing)
                    continue
                # If pending/cancelled, update scheduled_for to match current appointment time
                existing.scheduled_for = target_time
                existing.clinic_id = appointment.clinic_id
                if existing.status in ("cancelled", "failed") and existing.attempts < existing.max_attempts:
                    existing.status = "pending"
                db.add(existing)
                created_or_updated.append(existing)
            else:
                reminder = AppointmentReminder(
                    clinic_id=appointment.clinic_id,
                    appointment_id=appointment.id,
                    reminder_type=reminder_type,
                    scheduled_for=target_time,
                    status="pending",
                    attempts=0,
                    max_attempts=3,
                )
                db.add(reminder)
                created_or_updated.append(reminder)

        db.commit()
        for r in created_or_updated:
            db.refresh(r)
        logger.info(
            "Scheduled %d reminders for appointment %s (clinic %s)",
            len(created_or_updated),
            appointment.id,
            appointment.clinic_id,
        )
        return created_or_updated

    @classmethod
    def handle_appointment_rescheduled(
        cls,
        db: Session,
        appointment: Appointment,
    ) -> List[AppointmentReminder]:
        """
        Handles appointment rescheduling:
        Updates target times for unsent reminders and creates missing schedules.
        """
        logger.info("Rescheduling reminders for appointment %s", appointment.id)
        return cls.schedule_appointment_reminders(db, appointment)

    @classmethod
    def handle_appointment_cancelled_or_closed(
        cls,
        db: Session,
        appointment_id: uuid.UUID,
        reason: Optional[str] = None,
    ) -> int:
        """
        Cancels all pending or processing reminders for an appointment that has been cancelled/closed.
        """
        reminders = db.scalars(
            select(AppointmentReminder).where(
                AppointmentReminder.appointment_id == appointment_id,
                AppointmentReminder.status.in_(["pending", "processing"]),
            )
        ).all()

        cancelled_count = 0
        for r in reminders:
            r.status = "cancelled"
            r.error_code = "APPOINTMENT_CLOSED"
            r.error_message = reason or "Appointment was cancelled or closed before delivery"
            db.add(r)
            cancelled_count += 1

        if cancelled_count > 0:
            db.commit()
            logger.info("Cancelled %d pending reminders for appointment %s", cancelled_count, appointment_id)
        return cancelled_count

    @classmethod
    def get_reminders_for_appointment(
        cls,
        db: Session,
        clinic_id: uuid.UUID,
        appointment_id: uuid.UUID,
    ) -> List[AppointmentReminder]:
        """
        Retrieves all reminder records for a given appointment under tenant isolation.
        """
        return list(
            db.scalars(
                select(AppointmentReminder)
                .where(
                    AppointmentReminder.clinic_id == clinic_id,
                    AppointmentReminder.appointment_id == appointment_id,
                )
                .order_by(AppointmentReminder.scheduled_for.asc())
            ).all()
        )


    @classmethod
    async def process_due_reminders(
        cls,
        db: Session,
        current_time: Optional[datetime] = None,
        batch_size: int = 50,
    ) -> int:
        """
        Finds pending due reminders across clinics and dispatches them safely.
        """
        now = current_time or utc_now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        due_reminder_ids = db.scalars(
            select(AppointmentReminder.id)
            .where(
                AppointmentReminder.status == "pending",
                AppointmentReminder.scheduled_for <= now,
                AppointmentReminder.attempts < AppointmentReminder.max_attempts,
            )
            .order_by(AppointmentReminder.scheduled_for.asc())
            .limit(batch_size)
        ).all()

        if not due_reminder_ids:
            return 0

        logger.info("Discovered %d due reminders to process at %s", len(due_reminder_ids), now.isoformat())
        processed_count = 0

        for r_id in due_reminder_ids:
            success = await cls.claim_and_send_reminder(db=db, reminder_id=r_id, current_time=now)
            if success:
                processed_count += 1

        return processed_count

    @classmethod
    async def claim_and_send_reminder(
        cls,
        db: Session,
        reminder_id: uuid.UUID,
        current_time: Optional[datetime] = None,
    ) -> bool:
        """
        Atomically claims a single reminder and executes delivery over WhatsApp.
        Applies idempotency, status re-checking, patient contact validation, and bounded retry logic.
        """
        now = current_time or utc_now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        # 1. Atomic row claim using FOR UPDATE SKIP LOCKED
        try:
            reminder = db.scalar(
                select(AppointmentReminder)
                .where(
                    AppointmentReminder.id == reminder_id,
                    AppointmentReminder.status == "pending",
                )
                .with_for_update(skip_locked=True)
            )
        except Exception:
            # Fallback for dialects without SKIP LOCKED support (e.g., SQLite in-memory tests)
            reminder = db.scalar(
                select(AppointmentReminder).where(
                    AppointmentReminder.id == reminder_id,
                    AppointmentReminder.status == "pending",
                )
            )

        if not reminder:
            # Already claimed or no longer pending (Idempotency guarantee)
            return False

        # Mark as in-flight / processing
        reminder.status = "processing"
        reminder.attempts += 1
        reminder.last_attempt_at = now
        db.add(reminder)
        db.commit()
        db.refresh(reminder)

        logger.info(
            "Claimed reminder %s (%s) for appointment %s (attempt %d/%d)",
            reminder.id,
            reminder.reminder_type,
            reminder.appointment_id,
            reminder.attempts,
            reminder.max_attempts,
        )

        # 2. Re-check Appointment Eligibility
        appointment = db.scalar(
            select(Appointment).where(
                Appointment.id == reminder.appointment_id,
                Appointment.clinic_id == reminder.clinic_id,
            )
        )

        if not appointment or appointment.status not in ELIGIBLE_STATUSES:
            status_desc = appointment.status if appointment else "deleted"
            logger.info("Cancelling reminder %s because appointment status is '%s'", reminder.id, status_desc)
            reminder.status = "cancelled"
            reminder.error_code = "INELIGIBLE_STATUS"
            reminder.error_message = f"Appointment is in '{status_desc}' status"
            db.add(reminder)
            db.commit()
            return False

        # 3. Resolve Patient Lead & Contact Phone
        lead = None
        if appointment.lead_id:
            lead = db.scalar(
                select(Lead).where(
                    Lead.id == appointment.lead_id,
                    Lead.clinic_id == reminder.clinic_id,
                )
            )

        patient_phone = lead.phone if lead else None
        if not patient_phone or not patient_phone.strip():
            logger.warning("Permanent failure for reminder %s: Patient has no contact phone", reminder.id)
            reminder.status = "failed"
            reminder.failed_at = now
            reminder.error_code = "INVALID_CONTACT"
            reminder.error_message = "Patient has no valid WhatsApp phone number"
            db.add(reminder)
            db.commit()
            return False

        # 4. Resolve Clinic WhatsApp Account Credentials
        whatsapp_account = db.scalar(
            select(WhatsAppAccount).where(
                WhatsAppAccount.clinic_id == reminder.clinic_id,
                WhatsAppAccount.is_active == True,  # noqa: E712
            )
        )

        if not whatsapp_account:
            logger.error("No active WhatsApp account for clinic %s", reminder.clinic_id)
            if reminder.attempts >= reminder.max_attempts:
                reminder.status = "failed"
                reminder.failed_at = now
            else:
                reminder.status = "pending"
            reminder.error_code = "NO_WHATSAPP_ACCOUNT"
            reminder.error_message = "Clinic has no active WhatsApp account configured"
            db.add(reminder)
            db.commit()
            return False

        # 5. Retrieve Clinic Details for Message Personalization
        clinic = db.scalar(select(Clinic).where(Clinic.id == reminder.clinic_id))
        clinic_name = clinic.name if clinic else "Our Clinic"
        clinic_timezone = clinic.timezone if (clinic and clinic.timezone) else appointment.timezone or "Asia/Karachi"

        # 6. Render Message Text
        message_body = build_reminder_message(
            reminder_type=reminder.reminder_type,
            clinic_name=clinic_name,
            scheduled_at=appointment.scheduled_at,
            tz_name=clinic_timezone,
            patient_name=lead.full_name if lead else None,
            appointment_title=appointment.title,
        )

        # 7. Dispatch via Meta WhatsApp Cloud API Client
        whatsapp_client = WhatsAppClient(
            access_token=whatsapp_account.access_token,
            phone_number_id=whatsapp_account.phone_number_id,
        )

        try:
            outbound_res = await whatsapp_client.send_text_message(
                recipient_phone=patient_phone,
                message=message_body,
            )
            provider_msg_id = (
                outbound_res.messages[0].id
                if outbound_res and outbound_res.messages
                else f"wamid-reminder-{uuid.uuid4()}"
            )

            # Success
            reminder.status = "sent"
            reminder.sent_at = now
            reminder.provider_message_id = provider_msg_id
            reminder.error_code = None
            reminder.error_message = None
            db.add(reminder)
            db.commit()
            logger.info(
                "Successfully sent %s reminder %s for appointment %s (provider_id=%s)",
                reminder.reminder_type,
                reminder.id,
                reminder.appointment_id,
                provider_msg_id,
            )
            return True

        except (WhatsAppAuthenticationError, WhatsAppAPIError) as exc:
            # Check for permanent bad recipient errors (e.g. 400 Bad Request, recipient not on WhatsApp)
            error_str = str(exc)
            logger.error("WhatsApp API error sending reminder %s: %s", reminder.id, error_str)

            # Permanent failure classification
            is_permanent = "131030" in error_str or "100" in error_str or "invalid parameter" in error_str.lower()
            if is_permanent or reminder.attempts >= reminder.max_attempts:
                reminder.status = "failed"
                reminder.failed_at = now
            else:
                reminder.status = "pending"  # Eligible for retry

            reminder.error_code = "PROVIDER_ERROR"
            reminder.error_message = f"WhatsApp API delivery error: {error_str}"
            db.add(reminder)
            db.commit()
            return False

        except (WhatsAppNetworkError, WhatsAppRateLimitError, Exception) as exc:
            # Transient error - retry safe
            error_str = str(exc)
            logger.warning("Transient failure sending reminder %s: %s", reminder.id, error_str)
            if reminder.attempts >= reminder.max_attempts:
                reminder.status = "failed"
                reminder.failed_at = now
            else:
                reminder.status = "pending"  # Eligible for next retry cycle

            reminder.error_code = "TRANSIENT_NETWORK_ERROR"
            reminder.error_message = f"Network or rate limit failure: {error_str}"
            db.add(reminder)
            db.commit()
            return False


reminder_service = ReminderService()

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BadRequestException, NotFoundException, UnauthorizedException
from app.core.logging import logger
from app.core.security import (
    decrypt_token,
    encrypt_token,
    generate_oauth_state,
    verify_oauth_state,
)
from app.integrations.calendar.base import (
    CalendarAuthError,
    CalendarProvider,
    CalendarProviderError,
    CalendarRateLimitError,
)
from app.integrations.calendar.factory import get_calendar_provider
from app.models.appointment import Appointment
from app.models.calendar import CalendarConnection
from app.models.clinic import Clinic


class CalendarService:
    """
    Business service managing external calendar connections and appointment synchronization.
    Maintains strict multi-tenant isolation, token encryption, and idempotent synchronization.
    """

    def initiate_oauth(self, clinic_id: uuid.UUID, user_id: uuid.UUID, provider_name: str) -> str:
        """
        Builds the OAuth authorization URL with a secure, CSRF-protected state parameter.
        """
        provider = get_calendar_provider(provider_name)
        state = generate_oauth_state(clinic_id=clinic_id, user_id=user_id, provider=provider.provider_name)
        return provider.get_authorization_url(state=state)

    async def handle_oauth_callback(
        self,
        db: Session,
        provider_name: str,
        code: str,
        state: str,
    ) -> CalendarConnection:
        """
        Validates OAuth state, exchanges code for credentials, encrypts tokens, and stores connection.
        """
        state_payload = verify_oauth_state(state, expected_provider=provider_name)
        clinic_id = uuid.UUID(state_payload["clinic_id"])

        provider = get_calendar_provider(provider_name)
        token_data = await provider.exchange_code(code)

        encrypted_access = encrypt_token(token_data["access_token"])
        encrypted_refresh = encrypt_token(token_data.get("refresh_token")) if token_data.get("refresh_token") else None

        # Check existing connection for this clinic and provider
        stmt = select(CalendarConnection).where(
            CalendarConnection.clinic_id == clinic_id,
            CalendarConnection.provider == provider.provider_name,
        )
        connection = db.scalar(stmt)

        now = datetime.now(timezone.utc)
        if connection:
            connection.encrypted_access_token = encrypted_access
            if encrypted_refresh:
                connection.encrypted_refresh_token = encrypted_refresh
            connection.token_expires_at = token_data.get("token_expires_at")
            connection.account_identifier = token_data.get("account_identifier") or connection.account_identifier
            connection.status = "connected"
            connection.last_error = None
            connection.connected_at = now
        else:
            connection = CalendarConnection(
                clinic_id=clinic_id,
                provider=provider.provider_name,
                account_identifier=token_data.get("account_identifier"),
                calendar_identifier="primary",
                calendar_name="Primary Calendar",
                encrypted_access_token=encrypted_access,
                encrypted_refresh_token=encrypted_refresh,
                token_expires_at=token_data.get("token_expires_at"),
                status="connected",
                connected_at=now,
            )
            db.add(connection)

        db.commit()
        db.refresh(connection)
        logger.info(
            "Calendar connection established | clinic_id=%s | provider=%s | account=%s",
            str(clinic_id),
            provider.provider_name,
            connection.account_identifier,
        )
        return connection

    def get_clinic_connections(self, db: Session, clinic_id: uuid.UUID) -> List[CalendarConnection]:
        """
        Returns all calendar connections for a given clinic.
        """
        stmt = select(CalendarConnection).where(
            CalendarConnection.clinic_id == clinic_id
        ).order_by(CalendarConnection.created_at)
        return list(db.scalars(stmt).all())

    def get_connection(
        self,
        db: Session,
        clinic_id: uuid.UUID,
        provider_name: str,
    ) -> Optional[CalendarConnection]:
        """
        Returns the calendar connection for a specific provider in a clinic.
        """
        stmt = select(CalendarConnection).where(
            CalendarConnection.clinic_id == clinic_id,
            CalendarConnection.provider == provider_name.lower().strip(),
        )
        return db.scalar(stmt)

    async def disconnect(self, db: Session, clinic_id: uuid.UUID, provider_name: str) -> CalendarConnection:
        """
        Safely disconnects an external calendar provider, invalidating/clearing stored tokens.
        Preserves internal CRM appointments and reminders.
        """
        connection = self.get_connection(db, clinic_id, provider_name)
        if not connection:
            raise NotFoundException(f"No {provider_name} calendar connection found for this clinic.")

        connection.encrypted_access_token = ""
        connection.encrypted_refresh_token = None
        connection.status = "disconnected"
        connection.last_error = None
        db.commit()
        db.refresh(connection)
        logger.info("Calendar connection disconnected | clinic_id=%s | provider=%s", str(clinic_id), provider_name)
        return connection

    async def _ensure_valid_token(
        self,
        db: Session,
        connection: CalendarConnection,
    ) -> str:
        """
        Decrypted access token provider with automatic token refresh on expiration.
        """
        if connection.status != "connected":
            raise CalendarAuthError(
                f"Calendar connection is in '{connection.status}' state.",
                provider=connection.provider,
            )

        now = datetime.now(timezone.utc)
        # Check if token is expired (or about to expire within 60s)
        is_expired = False
        if connection.token_expires_at:
            expires_at = connection.token_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            is_expired = expires_at <= (now + timedelta(seconds=60))

        access_token = decrypt_token(connection.encrypted_access_token)

        if not is_expired and access_token:
            return access_token

        # Attempt token refresh
        refresh_token = decrypt_token(connection.encrypted_refresh_token) if connection.encrypted_refresh_token else None
        if not refresh_token:
            connection.status = "expired"
            connection.last_error = "Access token expired and no refresh token available."
            db.commit()
            raise CalendarAuthError(
                "Access token expired and no refresh token is available.",
                provider=connection.provider,
            )

        provider = get_calendar_provider(connection.provider)
        try:
            new_tokens = await provider.refresh_tokens(refresh_token)
            connection.encrypted_access_token = encrypt_token(new_tokens["access_token"])
            if new_tokens.get("refresh_token"):
                connection.encrypted_refresh_token = encrypt_token(new_tokens["refresh_token"])
            connection.token_expires_at = new_tokens.get("token_expires_at")
            connection.status = "connected"
            connection.last_error = None
            db.commit()
            return new_tokens["access_token"]
        except Exception as exc:
            connection.status = "error" if not isinstance(exc, CalendarAuthError) else "expired"
            connection.last_error = f"Token refresh failed: {str(exc)}"
            db.commit()
            raise

    async def list_available_calendars(
        self,
        db: Session,
        clinic_id: uuid.UUID,
        provider_name: str,
    ) -> List[Dict[str, Any]]:
        """
        Lists calendars from the connected provider for user selection.
        """
        connection = self.get_connection(db, clinic_id, provider_name)
        if not connection or connection.status != "connected":
            raise BadRequestException(f"Clinic is not connected to {provider_name} Calendar.")

        access_token = await self._ensure_valid_token(db, connection)
        provider = get_calendar_provider(connection.provider)
        return await provider.list_calendars(access_token)

    def select_calendar(
        self,
        db: Session,
        clinic_id: uuid.UUID,
        provider_name: str,
        calendar_identifier: str,
        calendar_name: Optional[str] = None,
    ) -> CalendarConnection:
        """
        Updates the selected target calendar for appointment synchronization.
        """
        connection = self.get_connection(db, clinic_id, provider_name)
        if not connection:
            raise NotFoundException(f"No {provider_name} connection found for this clinic.")

        connection.calendar_identifier = calendar_identifier
        connection.calendar_name = calendar_name or calendar_identifier
        db.commit()
        db.refresh(connection)
        return connection

    def _build_event_payload(self, appointment: Appointment) -> Dict[str, Any]:
        """
        Constructs a privacy-minimized calendar event dictionary.
        Does NOT leak internal AI prompts, raw conversation histories, or passwords.
        """
        start_time = appointment.scheduled_at
        end_time = start_time + timedelta(minutes=appointment.duration_minutes)

        patient_name = appointment.lead.full_name if appointment.lead and appointment.lead.full_name else "Patient"
        summary = f"Appointment: {appointment.title} — {patient_name}"

        lines = [
            f"Service / Procedure: {appointment.title}",
            f"Patient: {patient_name}",
        ]
        if appointment.lead and appointment.lead.phone:
            lines.append(f"Phone: {appointment.lead.phone}")
        if appointment.description:
            lines.append(f"Note: {appointment.description}")

        description = "\n".join(lines)

        return {
            "summary": summary,
            "description": description,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "timezone": appointment.timezone or "Asia/Karachi",
        }

    async def sync_appointment(self, db: Session, appointment: Appointment) -> None:
        """
        Synchronizes a single appointment with the clinic's active external calendar.
        Ensures idempotency (updates existing event rather than duplicating).
        """
        # Find active calendar connection for the clinic
        connections = self.get_clinic_connections(db, appointment.clinic_id)
        active_connection = next((c for c in connections if c.status == "connected"), None)

        if not active_connection:
            appointment.calendar_sync_status = "disconnected"
            appointment.calendar_sync_error = "No connected calendar integration for clinic."
            db.commit()
            return

        provider = get_calendar_provider(active_connection.provider)
        try:
            access_token = await self._ensure_valid_token(db, active_connection)
        except Exception as exc:
            appointment.calendar_sync_status = "failed"
            appointment.calendar_sync_error = f"Authentication error: {str(exc)}"
            appointment.calendar_retry_count += 1
            db.commit()
            return

        calendar_id = active_connection.calendar_identifier or "primary"

        try:
            # Handle cancellation / terminal state
            if appointment.status == "cancelled":
                if appointment.external_event_id:
                    await provider.delete_event(
                        access_token=access_token,
                        calendar_id=calendar_id,
                        event_id=appointment.external_event_id,
                    )
                    appointment.external_event_id = None
                appointment.calendar_sync_status = "synced"
                appointment.calendar_last_synced_at = datetime.now(timezone.utc)
                appointment.calendar_sync_error = None
                appointment.calendar_connection_id = active_connection.id
                db.commit()
                return

            # Handle creation or update
            event_payload = self._build_event_payload(appointment)
            if appointment.external_event_id:
                # Update existing event (idempotent / rescheduling)
                await provider.update_event(
                    access_token=access_token,
                    calendar_id=calendar_id,
                    event_id=appointment.external_event_id,
                    event_data=event_payload,
                )
            else:
                # Create new event
                event_id = await provider.create_event(
                    access_token=access_token,
                    calendar_id=calendar_id,
                    event_data=event_payload,
                )
                appointment.external_event_id = event_id

            appointment.calendar_connection_id = active_connection.id
            appointment.calendar_sync_status = "synced"
            appointment.calendar_last_synced_at = datetime.now(timezone.utc)
            appointment.calendar_sync_error = None
            appointment.calendar_retry_count = 0
            db.commit()
            logger.info(
                "Appointment synced with external calendar | appt_id=%s | event_id=%s | provider=%s",
                str(appointment.id),
                appointment.external_event_id,
                active_connection.provider,
            )

        except CalendarAuthError as exc:
            appointment.calendar_sync_status = "failed"
            appointment.calendar_sync_error = str(exc)
            appointment.calendar_retry_count += 1
            db.commit()
            logger.warning("Calendar sync auth failure: %s", str(exc))

        except CalendarRateLimitError as exc:
            appointment.calendar_sync_error = str(exc)
            appointment.calendar_retry_count += 1
            if appointment.calendar_retry_count >= settings.CALENDAR_MAX_RETRY_COUNT:
                appointment.calendar_sync_status = "failed"
            else:
                appointment.calendar_sync_status = "pending"
            db.commit()
            logger.warning("Calendar sync rate limit hit: %s", str(exc))

        except CalendarProviderError as exc:
            appointment.calendar_sync_error = str(exc)
            appointment.calendar_retry_count += 1
            if not exc.retryable or appointment.calendar_retry_count >= settings.CALENDAR_MAX_RETRY_COUNT:
                appointment.calendar_sync_status = "failed"
            else:
                appointment.calendar_sync_status = "pending"
            db.commit()
            logger.error("Calendar sync provider error: %s", str(exc))

        except Exception as exc:
            appointment.calendar_sync_error = f"Unexpected error: {str(exc)}"
            appointment.calendar_retry_count += 1
            if appointment.calendar_retry_count >= settings.CALENDAR_MAX_RETRY_COUNT:
                appointment.calendar_sync_status = "failed"
            else:
                appointment.calendar_sync_status = "pending"
            db.commit()
            logger.error("Unexpected error during calendar sync: %s", str(exc), exc_info=True)

    async def process_due_calendar_syncs(self, db: Session, limit: int = 50) -> int:
        """
        Background batch worker discovering and synchronizing pending appointments.
        Reuses existing background task loop without creating duplicate workers.
        """
        stmt = select(Appointment).where(
            Appointment.calendar_sync_status == "pending",
            Appointment.calendar_retry_count < settings.CALENDAR_MAX_RETRY_COUNT,
        ).order_by(Appointment.updated_at.desc()).limit(limit)

        appointments = list(db.scalars(stmt).all())
        count = 0
        for appt in appointments:
            await self.sync_appointment(db, appt)
            count += 1
        return count


calendar_service = CalendarService()

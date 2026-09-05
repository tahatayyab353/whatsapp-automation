import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.database import get_db
from app.integrations.whatsapp.exceptions import (
    WhatsAppAPIError,
    WhatsAppAuthenticationError,
    WhatsAppNetworkError,
)
from app.main import app
from app.models import (
    Appointment,
    AppointmentReminder,
    Base,
    Clinic,
    ClinicMembership,
    Conversation,
    Lead,
    User,
    WhatsAppAccount,
)
from app.models.base import utc_now
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.services.appointment_service import appointment_service
from app.services.reminder_service import reminder_service
from app.services.reminder_templates import build_reminder_message, format_localized_datetime


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with patch("app.services.reminder_scheduler.reminder_scheduler.start", new_callable=AsyncMock):
        with patch("app.services.reminder_scheduler.reminder_scheduler.stop", new_callable=AsyncMock):
            with TestClient(app) as test_client:
                yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_lead_extraction():
    with patch(
        "app.services.lead_extraction_service.lead_extraction_service.extract_lead_from_conversation",
        new_callable=AsyncMock,
    ) as mock_ext:
        mock_ext.return_value = None
        yield mock_ext


@pytest.fixture
def setup_clinic_and_appointments(db_session):
    # Clinic A
    clinic_a = Clinic(name="Karachi Dental Studio", slug="karachi-dental", timezone="Asia/Karachi")
    owner_a = User(email="owner@kds.pk", full_name="Dr. Tariq", is_active=True)
    staff_a = User(email="staff@kds.pk", full_name="Ali Staff", is_active=True)
    db_session.add_all([clinic_a, owner_a, staff_a])
    db_session.commit()

    db_session.add(ClinicMembership(clinic_id=clinic_a.id, user_id=owner_a.id, role="owner"))
    db_session.add(ClinicMembership(clinic_id=clinic_a.id, user_id=staff_a.id, role="staff"))

    # WhatsApp Account for Clinic A
    wa_account = WhatsAppAccount(
        clinic_id=clinic_a.id,
        phone_number="+923001234567",
        phone_number_id="1270146759520885",
        business_account_id="1398196068924367",
        access_token="test-waba-secret-access-token-xyz",
        is_active=True,
    )
    db_session.add(wa_account)

    lead_a = Lead(
        clinic_id=clinic_a.id,
        full_name="Farhan Qureshi",
        phone="+923005554433",
        email="farhan@example.com",
        service_interest="Scaling & Polishing",
        source="whatsapp",
        status="qualified",
    )
    db_session.add(lead_a)
    db_session.commit()

    # Clinic B for Tenant Isolation tests
    clinic_b = Clinic(name="Lahore Dental Care", slug="lahore-dental", timezone="Asia/Karachi")
    staff_b = User(email="staff@ldc.pk", full_name="Sara Staff B", is_active=True)
    db_session.add_all([clinic_b, staff_b])
    db_session.commit()
    db_session.add(ClinicMembership(clinic_id=clinic_b.id, user_id=staff_b.id, role="staff"))

    # Unaffiliated User (No Clinic Membership)
    user_unaffiliated = User(email="outsider@example.com", full_name="Outsider User", is_active=True)
    db_session.add(user_unaffiliated)
    db_session.commit()

    return {
        "clinic_a": clinic_a,
        "owner_a": owner_a,
        "staff_a": staff_a,
        "lead_a": lead_a,
        "wa_account": wa_account,
        "clinic_b": clinic_b,
        "staff_b": staff_b,
        "user_unaffiliated": user_unaffiliated,
    }


# ============================================================================
# 1. Eligible appointment creates 24h reminder
# ============================================================================
def test_1_eligible_appointment_creates_24h_reminder(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    appt_time = utc_now() + timedelta(days=2)

    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=AppointmentCreate(
            lead_id=data["lead_a"].id,
            title="Scaling & Polishing",
            scheduled_at=appt_time,
            duration_minutes=30,
            status="requested",
        ),
        created_by_user_id=data["staff_a"].id,
    )

    r24 = db_session.scalar(
        select(AppointmentReminder).where(
            AppointmentReminder.appointment_id == appt.id,
            AppointmentReminder.reminder_type == "APPOINTMENT_24H",
        )
    )
    assert r24 is not None
    assert r24.status == "pending"
    assert r24.attempts == 0
    assert r24.max_attempts == 3


# ============================================================================
# 2. Eligible appointment creates 2h reminder
# ============================================================================
def test_2_eligible_appointment_creates_2h_reminder(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    appt_time = utc_now() + timedelta(days=2)

    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=AppointmentCreate(
            lead_id=data["lead_a"].id,
            title="Scaling & Polishing",
            scheduled_at=appt_time,
            duration_minutes=30,
            status="confirmed",
        ),
        created_by_user_id=data["staff_a"].id,
    )

    r2 = db_session.scalar(
        select(AppointmentReminder).where(
            AppointmentReminder.appointment_id == appt.id,
            AppointmentReminder.reminder_type == "APPOINTMENT_2H",
        )
    )
    assert r2 is not None
    assert r2.status == "pending"
    assert r2.attempts == 0


# ============================================================================
# 3. Ineligible appointment creates no reminders
# ============================================================================
def test_3_ineligible_appointment_creates_no_reminders(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    appt = Appointment(
        clinic_id=data["clinic_a"].id,
        lead_id=data["lead_a"].id,
        title="Historical Appointment",
        scheduled_at=utc_now() + timedelta(days=1),
        duration_minutes=30,
        status="completed",
        timezone="Asia/Karachi",
    )
    db_session.add(appt)
    db_session.commit()

    reminders = reminder_service.schedule_appointment_reminders(db=db_session, appointment=appt)
    assert len(reminders) == 0

    count = db_session.scalar(
        select(AppointmentReminder).where(AppointmentReminder.appointment_id == appt.id)
    )
    assert count is None


# ============================================================================
# 4. 24h timing
# ============================================================================
def test_4_reminder_24h_timing(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    target_time = utc_now() + timedelta(days=3)

    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=AppointmentCreate(
            lead_id=data["lead_a"].id,
            title="Checkup",
            scheduled_at=target_time,
            duration_minutes=30,
            status="requested",
        ),
        created_by_user_id=data["staff_a"].id,
    )

    r24 = db_session.scalar(
        select(AppointmentReminder).where(
            AppointmentReminder.appointment_id == appt.id,
            AppointmentReminder.reminder_type == "APPOINTMENT_24H",
        )
    )
    assert r24 is not None
    r24_time = r24.scheduled_for if r24.scheduled_for.tzinfo else r24.scheduled_for.replace(tzinfo=timezone.utc)
    expected_time = target_time - timedelta(hours=24)
    assert abs((r24_time - expected_time).total_seconds()) < 5


# ============================================================================
# 5. 2h timing
# ============================================================================
def test_5_reminder_2h_timing(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    target_time = utc_now() + timedelta(days=3)

    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=AppointmentCreate(
            lead_id=data["lead_a"].id,
            title="Checkup",
            scheduled_at=target_time,
            duration_minutes=30,
            status="requested",
        ),
        created_by_user_id=data["staff_a"].id,
    )

    r2 = db_session.scalar(
        select(AppointmentReminder).where(
            AppointmentReminder.appointment_id == appt.id,
            AppointmentReminder.reminder_type == "APPOINTMENT_2H",
        )
    )
    assert r2 is not None
    r2_time = r2.scheduled_for if r2.scheduled_for.tzinfo else r2.scheduled_for.replace(tzinfo=timezone.utc)
    expected_time = target_time - timedelta(hours=2)
    assert abs((r2_time - expected_time).total_seconds()) < 5


# ============================================================================
# 6. Timezone conversion
# ============================================================================
def test_6_timezone_conversion_in_reminder_messages():
    # 09:30 UTC is 14:30 PKT (02:30 PM) in Asia/Karachi (UTC+5)
    scheduled_utc = datetime(2026, 9, 10, 9, 30, tzinfo=timezone.utc)
    date_str, time_str = format_localized_datetime(scheduled_utc, tz_name="Asia/Karachi")

    assert "Sep 10, 2026" in date_str
    assert time_str == "02:30 PM"

    msg = build_reminder_message(
        reminder_type="APPOINTMENT_24H",
        clinic_name="Karachi Dental Studio",
        scheduled_at=scheduled_utc,
        tz_name="Asia/Karachi",
        patient_name="Farhan",
        appointment_title="Root Canal",
    )
    assert "02:30 PM" in msg
    assert "Karachi Dental Studio" in msg
    assert "Root Canal" in msg


# ============================================================================
# 7. Cancellation prevents 24h delivery
# ============================================================================
def test_7_cancellation_prevents_24h_delivery(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=AppointmentCreate(
            lead_id=data["lead_a"].id,
            title="Scaling",
            scheduled_at=utc_now() + timedelta(days=2),
            duration_minutes=30,
            status="confirmed",
        ),
        created_by_user_id=data["staff_a"].id,
    )

    appointment_service.cancel_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        appointment_id=appt.id,
        reason="Patient illness",
    )

    r24 = db_session.scalar(
        select(AppointmentReminder).where(
            AppointmentReminder.appointment_id == appt.id,
            AppointmentReminder.reminder_type == "APPOINTMENT_24H",
        )
    )
    assert r24.status == "cancelled"
    assert r24.error_code == "APPOINTMENT_CLOSED"

    # Processing loop should not send cancelled reminders
    with patch("app.services.reminder_service.WhatsAppClient") as MockClient:
        sent_count = asyncio.run(reminder_service.process_due_reminders(db=db_session))
        assert sent_count == 0
        MockClient.return_value.send_text_message.assert_not_called()


# ============================================================================
# 8. Cancellation prevents 2h delivery
# ============================================================================
def test_8_cancellation_prevents_2h_delivery(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=AppointmentCreate(
            lead_id=data["lead_a"].id,
            title="Scaling",
            scheduled_at=utc_now() + timedelta(hours=1),
            duration_minutes=30,
            status="confirmed",
        ),
        created_by_user_id=data["staff_a"].id,
    )

    appointment_service.cancel_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        appointment_id=appt.id,
    )

    r2 = db_session.scalar(
        select(AppointmentReminder).where(
            AppointmentReminder.appointment_id == appt.id,
            AppointmentReminder.reminder_type == "APPOINTMENT_2H",
        )
    )
    assert r2.status == "cancelled"


# ============================================================================
# 9. Rescheduling invalidates obsolete reminders
# ============================================================================
def test_9_rescheduling_invalidates_obsolete_reminders(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    initial_time = utc_now() + timedelta(days=2)
    new_time = utc_now() + timedelta(days=5)

    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=AppointmentCreate(
            lead_id=data["lead_a"].id,
            title="Consultation",
            scheduled_at=initial_time,
            duration_minutes=30,
            status="confirmed",
        ),
        created_by_user_id=data["staff_a"].id,
    )

    r24_before = db_session.scalar(
        select(AppointmentReminder).where(
            AppointmentReminder.appointment_id == appt.id,
            AppointmentReminder.reminder_type == "APPOINTMENT_24H",
        )
    )
    old_target = r24_before.scheduled_for

    # Update appointment time
    appointment_service.update_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        appointment_id=appt.id,
        payload=AppointmentUpdate(scheduled_at=new_time),
    )

    db_session.refresh(r24_before)
    # The obsolete scheduled_for is updated
    assert r24_before.scheduled_for != old_target


# ============================================================================
# 10. Rescheduling creates the new reminder schedule
# ============================================================================
def test_10_rescheduling_creates_new_reminder_schedule(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    initial_time = utc_now() + timedelta(days=2)
    new_time = utc_now() + timedelta(days=5)

    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=AppointmentCreate(
            lead_id=data["lead_a"].id,
            title="Consultation",
            scheduled_at=initial_time,
            duration_minutes=30,
            status="confirmed",
        ),
        created_by_user_id=data["staff_a"].id,
    )

    appointment_service.update_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        appointment_id=appt.id,
        payload=AppointmentUpdate(scheduled_at=new_time),
    )

    reminders = db_session.scalars(
        select(AppointmentReminder).where(AppointmentReminder.appointment_id == appt.id)
    ).all()
    assert len(reminders) == 2

    r24 = next(r for r in reminders if r.reminder_type == "APPOINTMENT_24H")
    r2 = next(r for r in reminders if r.reminder_type == "APPOINTMENT_2H")

    r24_time = r24.scheduled_for if r24.scheduled_for.tzinfo else r24.scheduled_for.replace(tzinfo=timezone.utc)
    r2_time = r2.scheduled_for if r2.scheduled_for.tzinfo else r2.scheduled_for.replace(tzinfo=timezone.utc)

    assert abs((r24_time - (new_time - timedelta(hours=24))).total_seconds()) < 5
    assert abs((r2_time - (new_time - timedelta(hours=2))).total_seconds()) < 5


# ============================================================================
# 11. Same reminder cannot be sent twice
# ============================================================================
def test_11_same_reminder_cannot_be_sent_twice(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    appt_time = utc_now() + timedelta(hours=1)

    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=AppointmentCreate(
            lead_id=data["lead_a"].id,
            title="Scaling",
            scheduled_at=appt_time,
            duration_minutes=30,
            status="confirmed",
        ),
        created_by_user_id=data["staff_a"].id,
    )

    with patch("app.services.reminder_service.WhatsAppClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.send_text_message = AsyncMock()
        mock_response = AsyncMock()
        mock_msg = AsyncMock()
        mock_msg.id = "wamid.SEND_ONCE_TEST_123"
        mock_response.messages = [mock_msg]
        mock_instance.send_text_message.return_value = mock_response

        # First run: both 24h and 2h are due (appt is in 1h), so both are sent (sent_first == 2)
        sent_first = asyncio.run(reminder_service.process_due_reminders(db=db_session))
        assert sent_first == 2
        assert mock_instance.send_text_message.call_count == 2

        # Second run: both are already status='sent', must NOT send again
        sent_second = asyncio.run(reminder_service.process_due_reminders(db=db_session))
        assert sent_second == 0
        assert mock_instance.send_text_message.call_count == 2



# ============================================================================
# 12. Concurrent processing cannot duplicate delivery
# ============================================================================
def test_12_concurrent_processing_cannot_duplicate_delivery(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    appt_time = utc_now() + timedelta(hours=1)

    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=AppointmentCreate(
            lead_id=data["lead_a"].id,
            title="Scaling",
            scheduled_at=appt_time,
            duration_minutes=30,
            status="confirmed",
        ),
        created_by_user_id=data["staff_a"].id,
    )

    r24 = db_session.scalar(
        select(AppointmentReminder).where(
            AppointmentReminder.appointment_id == appt.id,
            AppointmentReminder.reminder_type == "APPOINTMENT_24H",
        )
    )

    with patch("app.services.reminder_service.WhatsAppClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.send_text_message = AsyncMock()
        mock_response = AsyncMock()
        mock_msg = AsyncMock()
        mock_msg.id = "wamid.CONCURRENT_LOCK_TEST"
        mock_response.messages = [mock_msg]
        mock_instance.send_text_message.return_value = mock_response

        # Worker 1 claims and sends
        res1 = asyncio.run(reminder_service.claim_and_send_reminder(db=db_session, reminder_id=r24.id))
        assert res1 is True

        # Worker 2 tries to claim the same reminder (which is now status='sent')
        res2 = asyncio.run(reminder_service.claim_and_send_reminder(db=db_session, reminder_id=r24.id))
        assert res2 is False

        # Client send_text_message was invoked exactly once
        assert mock_instance.send_text_message.call_count == 1


# ============================================================================
# 13. Transient provider failure retries
# ============================================================================
def test_13_transient_provider_failure_retries(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    appt_time = utc_now() + timedelta(hours=1)

    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=AppointmentCreate(
            lead_id=data["lead_a"].id,
            title="Scaling",
            scheduled_at=appt_time,
            duration_minutes=30,
            status="confirmed",
        ),
        created_by_user_id=data["staff_a"].id,
    )

    with patch("app.services.reminder_service.WhatsAppClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.send_text_message = AsyncMock(side_effect=WhatsAppNetworkError("Connection timed out"))

        # Attempt 1
        asyncio.run(reminder_service.process_due_reminders(db=db_session))
        r24 = db_session.scalar(
            select(AppointmentReminder).where(
                AppointmentReminder.appointment_id == appt.id,
                AppointmentReminder.reminder_type == "APPOINTMENT_24H",
            )
        )
        assert r24.status == "pending"
        assert r24.attempts == 1
        assert r24.error_code == "TRANSIENT_NETWORK_ERROR"

        # Attempt 2
        asyncio.run(reminder_service.process_due_reminders(db=db_session))
        db_session.refresh(r24)
        assert r24.status == "pending"
        assert r24.attempts == 2


# ============================================================================
# 14. Retry count is bounded
# ============================================================================
def test_14_retry_count_is_bounded(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    appt_time = utc_now() + timedelta(hours=1)

    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=AppointmentCreate(
            lead_id=data["lead_a"].id,
            title="Scaling",
            scheduled_at=appt_time,
            duration_minutes=30,
            status="confirmed",
        ),
        created_by_user_id=data["staff_a"].id,
    )

    with patch("app.services.reminder_service.WhatsAppClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.send_text_message = AsyncMock(side_effect=Exception("Repeated 500 error"))

        # Run 3 attempts
        asyncio.run(reminder_service.process_due_reminders(db=db_session))
        asyncio.run(reminder_service.process_due_reminders(db=db_session))
        asyncio.run(reminder_service.process_due_reminders(db=db_session))

        r24 = db_session.scalar(
            select(AppointmentReminder).where(
                AppointmentReminder.appointment_id == appt.id,
                AppointmentReminder.reminder_type == "APPOINTMENT_24H",
            )
        )
        assert r24.status == "failed"
        assert r24.attempts == 3
        assert r24.failed_at is not None

        # 4th run should not attempt it anymore
        mock_instance.send_text_message.reset_mock()
        asyncio.run(reminder_service.process_due_reminders(db=db_session))
        mock_instance.send_text_message.assert_not_called()


# ============================================================================
# 15. Permanent provider failure is not endlessly retried
# ============================================================================
def test_15_permanent_provider_failure_is_not_endlessly_retried(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    appt_time = utc_now() + timedelta(hours=1)

    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=AppointmentCreate(
            lead_id=data["lead_a"].id,
            title="Scaling",
            scheduled_at=appt_time,
            duration_minutes=30,
            status="confirmed",
        ),
        created_by_user_id=data["staff_a"].id,
    )

    with patch("app.services.reminder_service.WhatsAppClient") as MockClient:
        mock_instance = MockClient.return_value
        # 131030 is Meta's error code for invalid/non-WhatsApp recipient
        mock_instance.send_text_message = AsyncMock(
            side_effect=WhatsAppAPIError("Meta API Error 131030: Recipient is not a valid WhatsApp user")
        )

        asyncio.run(reminder_service.process_due_reminders(db=db_session))

        r24 = db_session.scalar(
            select(AppointmentReminder).where(
                AppointmentReminder.appointment_id == appt.id,
                AppointmentReminder.reminder_type == "APPOINTMENT_24H",
            )
        )
        # Immediately marked failed on attempt 1 without retrying
        assert r24.status == "failed"
        assert r24.attempts == 1
        assert r24.failed_at is not None
        assert r24.error_code == "PROVIDER_ERROR"


# ============================================================================
# 16. Clinic A cannot access Clinic B reminders
# ============================================================================
def test_16_clinic_a_cannot_access_clinic_b_reminders(client, db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    # Create Lead specifically belonging to Clinic B
    lead_b = Lead(
        clinic_id=data["clinic_b"].id,
        full_name="Clinic B Patient",
        phone="+923009998877",
        status="qualified",
    )
    db_session.add(lead_b)
    db_session.commit()

    appt_b = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_b"].id,
        payload=AppointmentCreate(
            lead_id=lead_b.id,
            title="Clinic B Appt",
            scheduled_at=utc_now() + timedelta(days=2),
            duration_minutes=30,
            status="confirmed",
        ),
        created_by_user_id=data["staff_b"].id,
    )

    # Staff A token for Clinic A
    token_a = create_access_token(subject=str(data["staff_a"].id))
    headers_a = {
        "Authorization": f"Bearer {token_a}",
        "X-Clinic-ID": str(data["clinic_a"].id),
    }

    # Staff A trying to get Clinic B's appointment reminders -> 404
    res = client.get(f"/api/v1/appointments/{appt_b.id}/reminders", headers=headers_a)
    assert res.status_code == 404


# ============================================================================
# 17. Dashboard/appointment reminder information is tenant-scoped
# ============================================================================
def test_17_dashboard_appointment_reminder_information_tenant_scoped(client, db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    appt_a = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=AppointmentCreate(
            lead_id=data["lead_a"].id,
            title="Clinic A Appt",
            scheduled_at=utc_now() + timedelta(days=2),
            duration_minutes=30,
            status="confirmed",
        ),
        created_by_user_id=data["staff_a"].id,
    )

    token_a = create_access_token(subject=str(data["staff_a"].id))
    headers_a = {
        "Authorization": f"Bearer {token_a}",
        "X-Clinic-ID": str(data["clinic_a"].id),
    }

    res = client.get(f"/api/v1/appointments/{appt_a.id}/reminders", headers=headers_a)
    assert res.status_code == 200
    reminders = res.json()
    assert len(reminders) == 2
    for r in reminders:
        assert r["clinic_id"] == str(data["clinic_a"].id)


# ============================================================================
# 18. Unauthenticated request rejected
# ============================================================================
def test_18_unauthenticated_request_rejected(client, db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=AppointmentCreate(
            lead_id=data["lead_a"].id,
            title="Open Appt",
            scheduled_at=utc_now() + timedelta(days=2),
            duration_minutes=30,
            status="confirmed",
        ),
        created_by_user_id=data["staff_a"].id,
    )

    res = client.get(f"/api/v1/appointments/{appt.id}/reminders")
    assert res.status_code == 401


# ============================================================================
# 19. Missing X-Clinic-ID rejected
# ============================================================================
def test_19_missing_x_clinic_id_rejected(client, db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    # User who is member of multiple clinics (Clinic A and Clinic B)
    multi_user = User(email="multi@example.com", full_name="Multi Staff", is_active=True)
    db_session.add(multi_user)
    db_session.commit()
    db_session.add(ClinicMembership(clinic_id=data["clinic_a"].id, user_id=multi_user.id, role="staff"))
    db_session.add(ClinicMembership(clinic_id=data["clinic_b"].id, user_id=multi_user.id, role="staff"))
    db_session.commit()

    token = create_access_token(subject=str(multi_user.id))
    # No X-Clinic-ID header sent for multi-tenant user
    headers = {"Authorization": f"Bearer {token}"}

    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=AppointmentCreate(
            lead_id=data["lead_a"].id,
            title="Open Appt",
            scheduled_at=utc_now() + timedelta(days=2),
            duration_minutes=30,
            status="confirmed",
        ),
        created_by_user_id=data["staff_a"].id,
    )

    res = client.get(f"/api/v1/appointments/{appt.id}/reminders", headers=headers)
    assert res.status_code == 400
    assert "Missing required header 'X-Clinic-ID'" in res.json()["error"]["message"]



# ============================================================================
# 20. Unauthorized role rejected where applicable
# ============================================================================
def test_20_unauthorized_role_rejected_where_applicable(client, db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    # User with no membership in Clinic A
    outsider = data["user_unaffiliated"]
    token = create_access_token(subject=str(outsider.id))
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Clinic-ID": str(data["clinic_a"].id),
    }

    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=AppointmentCreate(
            lead_id=data["lead_a"].id,
            title="Private Appt",
            scheduled_at=utc_now() + timedelta(days=2),
            duration_minutes=30,
            status="confirmed",
        ),
        created_by_user_id=data["staff_a"].id,
    )

    res = client.get(f"/api/v1/appointments/{appt.id}/reminders", headers=headers)
    assert res.status_code == 403


# ============================================================================
# 21. Reminder API does not expose credentials
# ============================================================================
def test_21_reminder_api_does_not_expose_credentials(client, db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=AppointmentCreate(
            lead_id=data["lead_a"].id,
            title="Security Audit Appt",
            scheduled_at=utc_now() + timedelta(days=2),
            duration_minutes=30,
            status="confirmed",
        ),
        created_by_user_id=data["staff_a"].id,
    )

    token = create_access_token(subject=str(data["staff_a"].id))
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Clinic-ID": str(data["clinic_a"].id),
    }

    res = client.get(f"/api/v1/appointments/{appt.id}/reminders", headers=headers)
    assert res.status_code == 200
    reminders = res.json()
    for item in reminders:
        assert "access_token" not in item
        assert "secret" not in item
        assert "token" not in item
        assert "app_secret" not in item
        assert "password" not in item


# ============================================================================
# 22. Logs do not contain secrets
# ============================================================================
def test_22_logs_do_not_contain_secrets(db_session, setup_clinic_and_appointments, caplog):
    data = setup_clinic_and_appointments
    caplog.set_level(logging.DEBUG)

    secret_token = "test-waba-secret-access-token-xyz"
    appt_time = utc_now() + timedelta(hours=1)

    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=AppointmentCreate(
            lead_id=data["lead_a"].id,
            title="Audit Appointment",
            scheduled_at=appt_time,
            duration_minutes=30,
            status="confirmed",
        ),
        created_by_user_id=data["staff_a"].id,
    )

    with patch("app.services.reminder_service.WhatsAppClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.send_text_message = AsyncMock()
        mock_response = AsyncMock()
        mock_msg = AsyncMock()
        mock_msg.id = "wamid.LOG_AUDIT_123"
        mock_response.messages = [mock_msg]
        mock_instance.send_text_message.return_value = mock_response

        asyncio.run(reminder_service.process_due_reminders(db=db_session))

    all_logs = " ".join([record.getMessage() for record in caplog.records])
    assert secret_token not in all_logs

import asyncio
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
from app.services.reminder_templates import build_reminder_message


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
        access_token="test-waba-access-token",
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
    db_session.commit()

    return {
        "clinic_a": clinic_a,
        "owner_a": owner_a,
        "staff_a": staff_a,
        "lead_a": lead_a,
        "wa_account": wa_account,
        "clinic_b": clinic_b,
        "staff_b": staff_b,
    }


def test_schedule_reminders_on_appointment_creation(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    target_time = utc_now() + timedelta(days=2)

    appt_in = AppointmentCreate(
        lead_id=data["lead_a"].id,
        title="Scaling & Polishing",
        scheduled_at=target_time,
        duration_minutes=30,
        status="requested",
    )
    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=appt_in,
        created_by_user_id=data["staff_a"].id,
    )

    reminders = db_session.scalars(
        select(AppointmentReminder).where(AppointmentReminder.appointment_id == appt.id)
    ).all()

    assert len(reminders) == 2
    types = {r.reminder_type for r in reminders}
    assert types == {"APPOINTMENT_24H", "APPOINTMENT_2H"}

    r24 = next(r for r in reminders if r.reminder_type == "APPOINTMENT_24H")
    r2 = next(r for r in reminders if r.reminder_type == "APPOINTMENT_2H")

    r24_time = r24.scheduled_for if r24.scheduled_for.tzinfo else r24.scheduled_for.replace(tzinfo=timezone.utc)
    r2_time = r2.scheduled_for if r2.scheduled_for.tzinfo else r2.scheduled_for.replace(tzinfo=timezone.utc)
    assert abs((r24_time - (target_time - timedelta(hours=24))).total_seconds()) < 5
    assert abs((r2_time - (target_time - timedelta(hours=2))).total_seconds()) < 5



def test_schedule_reminders_idempotency(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    target_time = utc_now() + timedelta(days=2)

    appt_in = AppointmentCreate(
        lead_id=data["lead_a"].id,
        title="Checkup",
        scheduled_at=target_time,
        duration_minutes=30,
        status="confirmed",
    )
    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=appt_in,
        created_by_user_id=data["staff_a"].id,
    )

    # Call reminder_service directly again
    reminder_service.schedule_appointment_reminders(db=db_session, appointment=appt)
    reminder_service.schedule_appointment_reminders(db=db_session, appointment=appt)

    reminders = db_session.scalars(
        select(AppointmentReminder).where(AppointmentReminder.appointment_id == appt.id)
    ).all()
    assert len(reminders) == 2


def test_reminders_cancelled_on_appointment_cancel(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    appt_in = AppointmentCreate(
        lead_id=data["lead_a"].id,
        title="Scaling",
        scheduled_at=utc_now() + timedelta(days=2),
        duration_minutes=30,
        status="confirmed",
    )
    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=appt_in,
        created_by_user_id=data["staff_a"].id,
    )

    # Cancel appointment
    appointment_service.cancel_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        appointment_id=appt.id,
        reason="Patient requested cancellation",
    )

    reminders = db_session.scalars(
        select(AppointmentReminder).where(AppointmentReminder.appointment_id == appt.id)
    ).all()
    assert len(reminders) == 2
    for r in reminders:
        assert r.status == "cancelled"
        assert r.error_code == "APPOINTMENT_CLOSED"


def test_reminders_cancelled_on_appointment_completion_or_noshow(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    appt_in = AppointmentCreate(
        lead_id=data["lead_a"].id,
        title="Scaling",
        scheduled_at=utc_now() + timedelta(days=2),
        duration_minutes=30,
        status="confirmed",
    )
    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=appt_in,
        created_by_user_id=data["staff_a"].id,
    )

    # Complete appointment
    appointment_service.complete_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        appointment_id=appt.id,
        notes="Procedure completed smoothly",
    )

    reminders = db_session.scalars(
        select(AppointmentReminder).where(AppointmentReminder.appointment_id == appt.id)
    ).all()
    assert len(reminders) == 2
    for r in reminders:
        assert r.status == "cancelled"


def test_reminders_updated_on_rescheduling(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    initial_time = utc_now() + timedelta(days=2)
    new_time = utc_now() + timedelta(days=4)

    appt_in = AppointmentCreate(
        lead_id=data["lead_a"].id,
        title="Scaling",
        scheduled_at=initial_time,
        duration_minutes=30,
        status="confirmed",
    )
    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=appt_in,
        created_by_user_id=data["staff_a"].id,
    )

    # Reschedule
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


def test_reminder_processing_and_dispatch(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    appt_time = utc_now() + timedelta(hours=1)

    appt_in = AppointmentCreate(
        lead_id=data["lead_a"].id,
        title="Emergency Scaling",
        scheduled_at=appt_time,
        duration_minutes=30,
        status="confirmed",
    )
    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=appt_in,
        created_by_user_id=data["staff_a"].id,
    )

    # Mock WhatsAppClient
    with patch("app.services.reminder_service.WhatsAppClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.send_text_message = AsyncMock()
        mock_response = AsyncMock()
        mock_msg = AsyncMock()
        mock_msg.id = "wamid.HBgLMzkyMzAwNTU1NDQzMxUCMRIA"
        mock_response.messages = [mock_msg]
        mock_instance.send_text_message.return_value = mock_response

        # Process due reminders
        sent_count = asyncio.run(reminder_service.process_due_reminders(db=db_session))
        assert sent_count >= 1

        mock_instance.send_text_message.assert_called()

    # Verify reminder record transitioned to 'sent'
    r24 = db_session.scalar(
        select(AppointmentReminder).where(
            AppointmentReminder.appointment_id == appt.id,
            AppointmentReminder.reminder_type == "APPOINTMENT_24H",
        )
    )
    assert r24.status == "sent"
    assert r24.provider_message_id == "wamid.HBgLMzkyMzAwNTU1NDQzMxUCMRIA"
    assert r24.attempts == 1


def test_reminder_bounded_retries_transient_failure(db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    appt_time = utc_now() + timedelta(hours=1)

    appt_in = AppointmentCreate(
        lead_id=data["lead_a"].id,
        title="Scaling",
        scheduled_at=appt_time,
        duration_minutes=30,
        status="confirmed",
    )
    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=appt_in,
        created_by_user_id=data["staff_a"].id,
    )

    with patch("app.services.reminder_service.WhatsAppClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.send_text_message = AsyncMock(side_effect=Exception("Network connection timeout"))

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

        # Attempt 2
        asyncio.run(reminder_service.process_due_reminders(db=db_session))
        db_session.refresh(r24)
        assert r24.status == "pending"
        assert r24.attempts == 2

        # Attempt 3 (Max attempts reached -> marked failed)
        asyncio.run(reminder_service.process_due_reminders(db=db_session))
        db_session.refresh(r24)
        assert r24.status == "failed"
        assert r24.attempts == 3
        assert r24.failed_at is not None


def test_reminders_api_get_endpoint(client, db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    appt_in = AppointmentCreate(
        lead_id=data["lead_a"].id,
        title="Veneers Consultation",
        scheduled_at=utc_now() + timedelta(days=2),
        duration_minutes=45,
        status="confirmed",
    )
    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=appt_in,
        created_by_user_id=data["staff_a"].id,
    )

    token = create_access_token(subject=str(data["staff_a"].id))
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Clinic-ID": str(data["clinic_a"].id),
    }

    res = client.get(f"/api/v1/appointments/{appt.id}/reminders", headers=headers)
    assert res.status_code == 200
    reminders_json = res.json()
    assert len(reminders_json) == 2
    types = {r["reminder_type"] for r in reminders_json}
    assert types == {"APPOINTMENT_24H", "APPOINTMENT_2H"}


def test_reminders_tenant_isolation(client, db_session, setup_clinic_and_appointments):
    data = setup_clinic_and_appointments
    appt_in = AppointmentCreate(
        lead_id=data["lead_a"].id,
        title="Private Checkup",
        scheduled_at=utc_now() + timedelta(days=2),
        duration_minutes=30,
        status="confirmed",
    )
    appt_a = appointment_service.create_appointment(
        db=db_session,
        clinic_id=data["clinic_a"].id,
        payload=appt_in,
        created_by_user_id=data["staff_a"].id,
    )

    # Token for Staff B (Clinic B)
    token_b = create_access_token(subject=str(data["staff_b"].id))
    headers_b = {
        "Authorization": f"Bearer {token_b}",
        "X-Clinic-ID": str(data["clinic_b"].id),
    }

    # Attempting to fetch Clinic A's reminders with Clinic B's token should yield 404
    res = client.get(f"/api/v1/appointments/{appt_a.id}/reminders", headers=headers_b)
    assert res.status_code == 404



def test_reminder_template_formatting():
    scheduled_utc = datetime(2026, 9, 6, 9, 30, tzinfo=timezone.utc)
    # In Asia/Karachi (UTC+5), 09:30 UTC is 14:30 PKT (02:30 PM)

    msg_24h = build_reminder_message(
        reminder_type="APPOINTMENT_24H",
        clinic_name="Karachi Dental Studio",
        scheduled_at=scheduled_utc,
        tz_name="Asia/Karachi",
        patient_name="Farhan",
        appointment_title="Scaling & Polishing",
    )
    assert "Karachi Dental Studio" in msg_24h
    assert "tomorrow" in msg_24h
    assert "02:30 PM" in msg_24h
    assert "Farhan" in msg_24h

    msg_2h = build_reminder_message(
        reminder_type="APPOINTMENT_2H",
        clinic_name="Karachi Dental Studio",
        scheduled_at=scheduled_utc,
        tz_name="Asia/Karachi",
        patient_name="Farhan",
        appointment_title="Scaling & Polishing",
    )
    assert "in about 2 hours" in msg_2h
    assert "02:30 PM" in msg_2h

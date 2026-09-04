from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.database import get_db
from app.main import app
from app.models import (
    Appointment,
    Base,
    Clinic,
    ClinicMembership,
    Conversation,
    Handoff,
    Lead,
    Message,
    User,
    WhatsAppAccount,
)
from app.models.base import utc_now


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
def setup_dashboard_data(db_session):
    now = utc_now()
    # Clinic A: Karachi Dental Studio
    clinic_a = Clinic(name="Karachi Dental Studio", slug="karachi-dental", timezone="Asia/Karachi")
    owner_a = User(email="owner@kds.pk", full_name="Dr. Tariq", is_active=True)
    staff_a = User(email="staff@kds.pk", full_name="Ali Staff", is_active=True)
    db_session.add_all([clinic_a, owner_a, staff_a])
    db_session.commit()

    db_session.add(ClinicMembership(clinic_id=clinic_a.id, user_id=owner_a.id, role="owner"))
    db_session.add(ClinicMembership(clinic_id=clinic_a.id, user_id=staff_a.id, role="staff"))

    # Clinic A WhatsApp account
    whatsapp_a = WhatsAppAccount(
        clinic_id=clinic_a.id,
        phone_number="+923001234567",
        phone_number_id="phone_id_clinic_a",
        business_account_id="waba_id_clinic_a",
        display_name="Karachi Dental Official",
        access_token="clinic_a_ultra_secret_access_token",
        is_active=True,
    )
    db_session.add(whatsapp_a)

    # Clinic A Leads
    lead_a1 = Lead(
        clinic_id=clinic_a.id,
        full_name="Farhan Qureshi",
        phone="+923005554433",
        email="farhan@example.com",
        service_interest="Teeth Cleaning",
        status="qualified",
    )
    lead_a2 = Lead(
        clinic_id=clinic_a.id,
        full_name="Sara Khan",
        phone="+923009998877",
        email="sara@example.com",
        service_interest="Invisalign",
        status="new",
    )
    db_session.add_all([lead_a1, lead_a2])
    db_session.commit()

    # Clinic A Conversations & Messages
    conv_a = Conversation(clinic_id=clinic_a.id, lead_id=lead_a1.id, channel="whatsapp", status="human_required")
    db_session.add(conv_a)
    db_session.commit()

    msg_a = Message(
        clinic_id=clinic_a.id,
        conversation_id=conv_a.id,
        sender_type="customer",
        content="I need assistance with scaling price please",
        created_at=now,
    )
    db_session.add(msg_a)

    # Clinic A Handoff
    handoff_a = Handoff(
        clinic_id=clinic_a.id,
        conversation_id=conv_a.id,
        lead_id=lead_a1.id,
        status="pending",
        reason="customer_requested_human",
        notes="Customer asked to speak to staff",
        requested_at=now,
    )
    db_session.add(handoff_a)

    # Clinic A Appointments (1 today confirmed, 1 today requested, 1 next week)
    today_time1 = now + timedelta(hours=2)
    today_time2 = now + timedelta(hours=4)
    next_week = now + timedelta(days=7)

    appt_a1 = Appointment(
        clinic_id=clinic_a.id,
        lead_id=lead_a1.id,
        title="Scaling & Polishing",
        scheduled_at=today_time1,
        duration_minutes=30,
        status="confirmed",
    )
    appt_a2 = Appointment(
        clinic_id=clinic_a.id,
        lead_id=lead_a2.id,
        title="Invisalign Consult",
        scheduled_at=today_time2,
        duration_minutes=45,
        status="requested",
    )
    appt_a3 = Appointment(
        clinic_id=clinic_a.id,
        lead_id=lead_a1.id,
        title="Followup",
        scheduled_at=next_week,
        duration_minutes=15,
        status="confirmed",
    )
    db_session.add_all([appt_a1, appt_a2, appt_a3])
    db_session.commit()

    # Clinic B: Lahore Aesthetic Clinic (to verify tenant isolation)
    clinic_b = Clinic(name="Lahore Aesthetic Clinic", slug="lahore-aesthetic", timezone="Asia/Karachi")
    staff_b = User(email="staff@lahore.pk", full_name="Usman Staff", is_active=True)
    db_session.add_all([clinic_b, staff_b])
    db_session.commit()

    db_session.add(ClinicMembership(clinic_id=clinic_b.id, user_id=staff_b.id, role="staff"))

    lead_b = Lead(clinic_id=clinic_b.id, full_name="Babar Azam", phone="+923211112233", status="new")
    db_session.add(lead_b)
    db_session.commit()

    appt_b = Appointment(
        clinic_id=clinic_b.id,
        lead_id=lead_b.id,
        title="Clinic B Surgery",
        scheduled_at=today_time1,
        duration_minutes=60,
        status="confirmed",
    )
    db_session.add(appt_b)
    db_session.commit()

    return {
        "clinic_a": clinic_a,
        "owner_a": owner_a,
        "staff_a": staff_a,
        "clinic_b": clinic_b,
        "staff_b": staff_b,
    }


def auth_headers(user: User, clinic: Clinic) -> dict:
    token = create_access_token(subject=str(user.id))
    return {
        "Authorization": f"Bearer {token}",
        "X-Clinic-ID": str(clinic.id),
    }


# ============================================================================
# CHUNK 10 Dashboard Summary Tests
# ============================================================================


def test_authorized_staff_can_access_dashboard_summary(client, setup_dashboard_data):
    clinic_a = setup_dashboard_data["clinic_a"]
    staff_a = setup_dashboard_data["staff_a"]

    headers = auth_headers(staff_a, clinic_a)
    res = client.get("/api/v1/dashboard/summary", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["clinic_id"] == str(clinic_a.id)
    assert data["clinic_name"] == "Karachi Dental Studio"
    assert data["timezone"] == "Asia/Karachi"

    metrics = data["metrics"]
    assert metrics["total_leads"] == 2
    assert metrics["open_conversations"] == 1
    assert metrics["pending_handoffs"] == 1
    assert metrics["today_appointments"] == 2
    assert metrics["confirmed_appointments_today"] == 1


def test_unauthenticated_user_is_rejected(client, setup_dashboard_data):
    clinic_a = setup_dashboard_data["clinic_a"]
    res = client.get("/api/v1/dashboard/summary", headers={"X-Clinic-ID": str(clinic_a.id)})
    assert res.status_code == 401


def test_missing_clinic_id_is_rejected(client, setup_dashboard_data):
    staff_a = setup_dashboard_data["staff_a"]
    token = create_access_token(subject=str(staff_a.id))
    res = client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400


def test_user_cannot_access_another_clinic_dashboard(client, setup_dashboard_data):
    clinic_b = setup_dashboard_data["clinic_b"]
    staff_a = setup_dashboard_data["staff_a"]  # Member of Clinic A only

    # Staff A attempts to pass Clinic B's ID
    headers = auth_headers(staff_a, clinic_b)
    res = client.get("/api/v1/dashboard/summary", headers=headers)
    assert res.status_code == 403


def test_dashboard_counts_and_lists_are_strictly_tenant_scoped(client, setup_dashboard_data):
    clinic_a = setup_dashboard_data["clinic_a"]
    staff_a = setup_dashboard_data["staff_a"]

    headers = auth_headers(staff_a, clinic_a)
    res = client.get("/api/v1/dashboard/summary", headers=headers)
    assert res.status_code == 200
    data = res.json()

    # Clinic B has 1 lead and 1 appointment today, which must NOT be in Clinic A's summary
    assert data["metrics"]["total_leads"] == 2
    assert len(data["recent_leads"]) == 2
    lead_names = [l["full_name"] for l in data["recent_leads"]]
    assert "Babar Azam" not in lead_names

    # Today's appointments (must only show Clinic A's 2 appointments)
    assert len(data["today_appointments"]) == 2
    appt_titles = [a["title"] for a in data["today_appointments"]]
    assert "Clinic B Surgery" not in appt_titles
    assert "Scaling & Polishing" in appt_titles
    assert "Invisalign Consult" in appt_titles


def test_pending_handoffs_are_tenant_scoped(client, setup_dashboard_data):
    clinic_a = setup_dashboard_data["clinic_a"]
    staff_a = setup_dashboard_data["staff_a"]

    headers = auth_headers(staff_a, clinic_a)
    res = client.get("/api/v1/dashboard/summary", headers=headers)
    assert res.status_code == 200
    data = res.json()

    handoffs = data["pending_handoffs"]
    assert len(handoffs) == 1
    assert handoffs[0]["reason"] == "customer_requested_human"
    assert handoffs[0]["lead_name"] == "Farhan Qureshi"


def test_dashboard_does_not_expose_credentials_or_secrets(client, setup_dashboard_data):
    clinic_a = setup_dashboard_data["clinic_a"]
    staff_a = setup_dashboard_data["staff_a"]

    headers = auth_headers(staff_a, clinic_a)
    res = client.get("/api/v1/dashboard/summary", headers=headers)
    assert res.status_code == 200

    raw_text = res.text
    assert "clinic_a_ultra_secret_access_token" not in raw_text
    assert "access_token" not in raw_text
    assert "app_secret" not in raw_text


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
    Base,
    Clinic,
    ClinicMembership,
    Conversation,
    Handoff,
    Lead,
    User,
)
from app.models.base import utc_now
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.services.appointment_service import appointment_service
from app.services.handoff_service import handoff_service


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
def setup_appointment_data(db_session):
    # Clinic A: Karachi Dental Studio
    clinic_a = Clinic(name="Karachi Dental Studio", slug="karachi-dental", timezone="Asia/Karachi")
    owner_a = User(email="owner@kds.pk", full_name="Dr. Tariq", is_active=True)
    admin_a = User(email="admin@kds.pk", full_name="Dr. Sara Admin", is_active=True)
    staff_a = User(email="staff@kds.pk", full_name="Ali Staff", is_active=True)
    db_session.add_all([clinic_a, owner_a, admin_a, staff_a])
    db_session.commit()

    db_session.add(ClinicMembership(clinic_id=clinic_a.id, user_id=owner_a.id, role="owner"))
    db_session.add(ClinicMembership(clinic_id=clinic_a.id, user_id=admin_a.id, role="admin"))
    db_session.add(ClinicMembership(clinic_id=clinic_a.id, user_id=staff_a.id, role="staff"))

    lead_a = Lead(
        clinic_id=clinic_a.id,
        full_name="Farhan Qureshi",
        phone="+923005554433",
        email="farhan@example.com",
        service_interest="Scaling and Polishing",
        source="whatsapp",
        status="qualified",
    )
    db_session.add(lead_a)
    db_session.commit()

    conv_a = Conversation(
        clinic_id=clinic_a.id,
        lead_id=lead_a.id,
        channel="whatsapp",
        status="open",
    )
    db_session.add(conv_a)
    db_session.commit()

    # Clinic B: Lahore Aesthetic Clinic
    clinic_b = Clinic(name="Lahore Aesthetic Clinic", slug="lahore-aesthetic", timezone="Asia/Karachi")
    staff_b = User(email="staff@lahore.pk", full_name="Usman Staff", is_active=True)
    db_session.add_all([clinic_b, staff_b])
    db_session.commit()

    db_session.add(ClinicMembership(clinic_id=clinic_b.id, user_id=staff_b.id, role="staff"))
    lead_b = Lead(
        clinic_id=clinic_b.id,
        full_name="Babar Azam",
        phone="+923211112233",
        source="whatsapp",
        status="new",
    )
    db_session.add(lead_b)
    db_session.commit()

    conv_b = Conversation(
        clinic_id=clinic_b.id,
        lead_id=lead_b.id,
        channel="whatsapp",
        status="open",
    )
    db_session.add(conv_b)
    db_session.commit()

    return {
        "clinic_a": clinic_a,
        "owner_a": owner_a,
        "admin_a": admin_a,
        "staff_a": staff_a,
        "lead_a": lead_a,
        "conv_a": conv_a,
        "clinic_b": clinic_b,
        "staff_b": staff_b,
        "lead_b": lead_b,
        "conv_b": conv_b,
    }


def auth_headers(user: User, clinic: Clinic) -> dict:
    token = create_access_token(subject=str(user.id))
    return {
        "Authorization": f"Bearer {token}",
        "X-Clinic-ID": str(clinic.id),
    }


# ============================================================================
# CHUNK 9 Appointment System Tests
# ============================================================================


def test_appointment_model_creation_and_relationships(db_session, setup_appointment_data):
    clinic_a = setup_appointment_data["clinic_a"]
    lead_a = setup_appointment_data["lead_a"]
    conv_a = setup_appointment_data["conv_a"]
    staff_a = setup_appointment_data["staff_a"]

    future_time = utc_now() + timedelta(days=2)
    payload = AppointmentCreate(
        lead_id=lead_a.id,
        conversation_id=conv_a.id,
        title="Dental Implant Consultation",
        description="Patient wants implant pricing and checkup",
        scheduled_at=future_time,
        duration_minutes=45,
        status="requested",
        notes="First time visitor",
    )
    appointment = appointment_service.create_appointment(
        db=db_session,
        clinic_id=clinic_a.id,
        payload=payload,
        created_by_user_id=staff_a.id,
    )

    assert appointment.id is not None
    assert appointment.clinic_id == clinic_a.id
    assert appointment.lead_id == lead_a.id
    assert appointment.conversation_id == conv_a.id
    assert appointment.created_by_user_id == staff_a.id
    assert appointment.title == "Dental Implant Consultation"
    assert appointment.duration_minutes == 45
    assert appointment.status == "requested"
    assert appointment.timezone == "Asia/Karachi"


def test_owner_admin_and_staff_can_manage_appointments(client, db_session, setup_appointment_data):
    clinic_a = setup_appointment_data["clinic_a"]
    owner_a = setup_appointment_data["owner_a"]
    admin_a = setup_appointment_data["admin_a"]
    staff_a = setup_appointment_data["staff_a"]
    lead_a = setup_appointment_data["lead_a"]

    future_time = (utc_now() + timedelta(days=3)).isoformat()

    # 1. Staff creates appointment
    res_create = client.post(
        "/api/v1/appointments",
        headers=auth_headers(staff_a, clinic_a),
        json={
            "lead_id": str(lead_a.id),
            "title": "Teeth Whitening",
            "scheduled_at": future_time,
            "duration_minutes": 60,
        },
    )
    assert res_create.status_code == 201
    appt_id = res_create.json()["id"]

    # 2. Admin confirms appointment
    res_confirm = client.post(
        f"/api/v1/appointments/{appt_id}/confirm",
        headers=auth_headers(admin_a, clinic_a),
        json={"notes": "Confirmed by admin on call"},
    )
    assert res_confirm.status_code == 200
    assert res_confirm.json()["status"] == "confirmed"

    # 3. Owner views appointment
    res_get = client.get(
        f"/api/v1/appointments/{appt_id}",
        headers=auth_headers(owner_a, clinic_a),
    )
    assert res_get.status_code == 200
    assert res_get.json()["id"] == appt_id


def test_unauthorized_user_and_missing_headers_rejected(client, db_session, setup_appointment_data):
    clinic_a = setup_appointment_data["clinic_a"]
    staff_a = setup_appointment_data["staff_a"]

    # 1. Missing Authorization Bearer
    res1 = client.get("/api/v1/appointments", headers={"X-Clinic-ID": str(clinic_a.id)})
    assert res1.status_code == 401

    # 2. Missing X-Clinic-ID
    token = create_access_token(subject=str(staff_a.id))
    res2 = client.get("/api/v1/appointments", headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 400


def test_tenant_isolation_cross_clinic_access_forbidden(client, db_session, setup_appointment_data):
    clinic_a = setup_appointment_data["clinic_a"]
    clinic_b = setup_appointment_data["clinic_b"]
    staff_a = setup_appointment_data["staff_a"]
    staff_b = setup_appointment_data["staff_b"]
    lead_b = setup_appointment_data["lead_b"]

    # Create appointment in Clinic B
    future_time = utc_now() + timedelta(days=2)
    appt_b = appointment_service.create_appointment(
        db=db_session,
        clinic_id=clinic_b.id,
        payload=AppointmentCreate(
            lead_id=lead_b.id,
            title="Clinic B Procedure",
            scheduled_at=future_time,
        ),
    )

    # Staff A from Clinic A tries to access Clinic B's appointment
    headers_a = auth_headers(staff_a, clinic_a)

    res_get = client.get(f"/api/v1/appointments/{appt_b.id}", headers=headers_a)
    assert res_get.status_code == 404

    res_patch = client.patch(
        f"/api/v1/appointments/{appt_b.id}",
        headers=headers_a,
        json={"title": "Hacked Title"},
    )
    assert res_patch.status_code == 404

    res_cancel = client.post(f"/api/v1/appointments/{appt_b.id}/cancel", headers=headers_a)
    assert res_cancel.status_code == 404


def test_status_transitions_requested_to_confirmed_to_completed(client, db_session, setup_appointment_data):
    clinic_a = setup_appointment_data["clinic_a"]
    staff_a = setup_appointment_data["staff_a"]
    lead_a = setup_appointment_data["lead_a"]

    future_time = utc_now() + timedelta(days=1)
    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=clinic_a.id,
        payload=AppointmentCreate(
            lead_id=lead_a.id,
            title="Root Canal",
            scheduled_at=future_time,
            status="requested",
        ),
    )
    headers = auth_headers(staff_a, clinic_a)

    # 1. requested -> confirmed
    res_conf = client.post(f"/api/v1/appointments/{appt.id}/confirm", headers=headers)
    assert res_conf.status_code == 200
    assert res_conf.json()["status"] == "confirmed"

    # 2. confirmed -> completed
    res_comp = client.post(f"/api/v1/appointments/{appt.id}/complete", headers=headers)
    assert res_comp.status_code == 200
    assert res_comp.json()["status"] == "completed"


def test_status_transitions_confirmed_to_no_show(client, db_session, setup_appointment_data):
    clinic_a = setup_appointment_data["clinic_a"]
    staff_a = setup_appointment_data["staff_a"]
    lead_a = setup_appointment_data["lead_a"]

    future_time = utc_now() + timedelta(days=1)
    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=clinic_a.id,
        payload=AppointmentCreate(
            lead_id=lead_a.id,
            title="Root Canal",
            scheduled_at=future_time,
            status="confirmed",
        ),
    )
    headers = auth_headers(staff_a, clinic_a)

    res_ns = client.post(f"/api/v1/appointments/{appt.id}/no-show", headers=headers)
    assert res_ns.status_code == 200
    assert res_ns.json()["status"] == "no_show"


def test_status_transitions_cancelled_and_terminal_states(client, db_session, setup_appointment_data):
    clinic_a = setup_appointment_data["clinic_a"]
    staff_a = setup_appointment_data["staff_a"]
    lead_a = setup_appointment_data["lead_a"]

    future_time = utc_now() + timedelta(days=1)
    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=clinic_a.id,
        payload=AppointmentCreate(
            lead_id=lead_a.id,
            title="Checkup",
            scheduled_at=future_time,
            status="requested",
        ),
    )
    headers = auth_headers(staff_a, clinic_a)

    # Cancel appointment
    res_cancel = client.post(
        f"/api/v1/appointments/{appt.id}/cancel",
        headers=headers,
        json={"reason": "Patient requested cancellation"},
    )
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "cancelled"
    assert res_cancel.json()["cancelled_at"] is not None

    # Attempt invalid transition: cancelled -> confirmed
    res_invalid = client.post(f"/api/v1/appointments/{appt.id}/confirm", headers=headers)
    assert res_invalid.status_code == 400


def test_cannot_schedule_in_past(client, db_session, setup_appointment_data):
    clinic_a = setup_appointment_data["clinic_a"]
    staff_a = setup_appointment_data["staff_a"]
    lead_a = setup_appointment_data["lead_a"]

    past_time = (utc_now() - timedelta(days=2)).isoformat()
    headers = auth_headers(staff_a, clinic_a)

    res = client.post(
        "/api/v1/appointments",
        headers=headers,
        json={
            "lead_id": str(lead_a.id),
            "title": "Past Appointment",
            "scheduled_at": past_time,
        },
    )
    assert res.status_code == 400


def test_invalid_duration_rejected(client, db_session, setup_appointment_data):
    clinic_a = setup_appointment_data["clinic_a"]
    staff_a = setup_appointment_data["staff_a"]
    lead_a = setup_appointment_data["lead_a"]

    future_time = (utc_now() + timedelta(days=2)).isoformat()
    headers = auth_headers(staff_a, clinic_a)

    # Zero duration
    res1 = client.post(
        "/api/v1/appointments",
        headers=headers,
        json={
            "lead_id": str(lead_a.id),
            "title": "Zero Duration",
            "scheduled_at": future_time,
            "duration_minutes": 0,
        },
    )
    assert res1.status_code in [400, 422]

    # Negative duration
    res2 = client.post(
        "/api/v1/appointments",
        headers=headers,
        json={
            "lead_id": str(lead_a.id),
            "title": "Negative Duration",
            "scheduled_at": future_time,
            "duration_minutes": -30,
        },
    )
    assert res2.status_code in [400, 422]


def test_invalid_lead_id_rejected(client, db_session, setup_appointment_data):
    clinic_a = setup_appointment_data["clinic_a"]
    staff_a = setup_appointment_data["staff_a"]

    future_time = (utc_now() + timedelta(days=2)).isoformat()
    headers = auth_headers(staff_a, clinic_a)

    fake_lead_id = str(uuid.uuid4())
    res = client.post(
        "/api/v1/appointments",
        headers=headers,
        json={
            "lead_id": fake_lead_id,
            "title": "Fake Lead",
            "scheduled_at": future_time,
        },
    )
    assert res.status_code == 404


def test_list_appointments_filtering_by_status_and_lead(client, db_session, setup_appointment_data):
    clinic_a = setup_appointment_data["clinic_a"]
    staff_a = setup_appointment_data["staff_a"]
    lead_a = setup_appointment_data["lead_a"]

    t1 = utc_now() + timedelta(days=1)
    t2 = utc_now() + timedelta(days=2)
    t3 = utc_now() + timedelta(days=3)

    appt1 = appointment_service.create_appointment(
        db=db_session, clinic_id=clinic_a.id,
        payload=AppointmentCreate(lead_id=lead_a.id, title="Appt 1", scheduled_at=t1, status="requested")
    )
    appt2 = appointment_service.create_appointment(
        db=db_session, clinic_id=clinic_a.id,
        payload=AppointmentCreate(lead_id=lead_a.id, title="Appt 2", scheduled_at=t2, status="confirmed")
    )
    appt3 = appointment_service.create_appointment(
        db=db_session, clinic_id=clinic_a.id,
        payload=AppointmentCreate(lead_id=lead_a.id, title="Appt 3", scheduled_at=t3, status="cancelled")
    )

    headers = auth_headers(staff_a, clinic_a)

    # Filter by status=confirmed
    res_status = client.get("/api/v1/appointments?status=confirmed", headers=headers)
    assert res_status.status_code == 200
    data = res_status.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == str(appt2.id)

    # Filter by lead_id
    res_lead = client.get(f"/api/v1/appointments?lead_id={lead_a.id}", headers=headers)
    assert res_lead.status_code == 200
    assert res_lead.json()["total"] == 3


def test_idempotent_appointment_request_prevents_duplicates(db_session, setup_appointment_data):
    clinic_a = setup_appointment_data["clinic_a"]
    lead_a = setup_appointment_data["lead_a"]
    conv_a = setup_appointment_data["conv_a"]

    req_time = utc_now() + timedelta(days=2)

    # First call
    a1 = appointment_service.create_appointment_request_from_ai(
        db=db_session,
        clinic_id=clinic_a.id,
        lead_id=lead_a.id,
        conversation_id=conv_a.id,
        scheduled_at=req_time,
        title="Consultation Request",
    )

    # Immediate retry with same parameters
    a2 = appointment_service.create_appointment_request_from_ai(
        db=db_session,
        clinic_id=clinic_a.id,
        lead_id=lead_a.id,
        conversation_id=conv_a.id,
        scheduled_at=req_time,
        title="Consultation Request",
    )

    assert a1.id == a2.id
    all_appts = db_session.scalars(select(Appointment).where(Appointment.clinic_id == clinic_a.id)).all()
    assert len(all_appts) == 1


def test_appointment_request_preserved_during_human_handoff(db_session, setup_appointment_data):
    clinic_a = setup_appointment_data["clinic_a"]
    lead_a = setup_appointment_data["lead_a"]
    conv_a = setup_appointment_data["conv_a"]

    # 1. Create appointment request
    req_time = utc_now() + timedelta(days=1)
    appt = appointment_service.create_appointment(
        db=db_session,
        clinic_id=clinic_a.id,
        payload=AppointmentCreate(
            lead_id=lead_a.id,
            conversation_id=conv_a.id,
            title="Scaling Request",
            scheduled_at=req_time,
            status="requested",
        ),
    )

    # 2. Trigger human handoff
    handoff = handoff_service.request_handoff(
        db=db_session,
        clinic_id=clinic_a.id,
        conversation_id=conv_a.id,
        reason="customer_requested_human",
    )

    # 3. Verify appointment remains intact
    db_session.refresh(appt)
    assert appt.status == "requested"
    assert appt.conversation_id == conv_a.id
    assert handoff.conversation_id == conv_a.id


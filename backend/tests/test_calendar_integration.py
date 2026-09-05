from datetime import datetime, timedelta, timezone
import json
from unittest.mock import AsyncMock, patch
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decrypt_token,
    encrypt_token,
    generate_oauth_state,
    hash_password,
    verify_oauth_state,
)
from app.db.database import get_db
from app.integrations.calendar.base import (
    CalendarAuthError,
    CalendarProviderError,
    CalendarRateLimitError,
)
from app.main import app
from app.models import (
    Appointment,
    Base,
    CalendarConnection,
    Clinic,
    ClinicMembership,
    Lead,
    User,
)
from app.services.calendar_service import calendar_service


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


@pytest.fixture
def setup_tenants(db_session):
    # Clinic A
    clinic_a = Clinic(name="Karachi Dental Studio", slug="karachi-dental", timezone="Asia/Karachi")
    user_a = User(email="owner@kds.local", full_name="Dr. Tariq", is_active=True, password_hash=hash_password("Secret123!"))
    staff_a = User(email="staff@kds.local", full_name="Nurse Sara", is_active=True, password_hash=hash_password("Secret123!"))
    unauth_user = User(email="intruder@external.local", full_name="Intruder", is_active=True, password_hash=hash_password("Secret123!"))

    db_session.add_all([clinic_a, user_a, staff_a, unauth_user])
    db_session.flush()

    mem_owner_a = ClinicMembership(clinic_id=clinic_a.id, user_id=user_a.id, role="owner")
    mem_staff_a = ClinicMembership(clinic_id=clinic_a.id, user_id=staff_a.id, role="staff")

    # Clinic B
    clinic_b = Clinic(name="Lahore Aesthetic Clinic", slug="lahore-aesthetic", timezone="Asia/Karachi")
    user_b = User(email="owner@lahore.local", full_name="Dr. Zaid", is_active=True, password_hash=hash_password("Secret123!"))
    db_session.add_all([clinic_b, user_b, mem_owner_a, mem_staff_a])
    db_session.flush()

    mem_owner_b = ClinicMembership(clinic_id=clinic_b.id, user_id=user_b.id, role="owner")
    db_session.add(mem_owner_b)

    # Lead and appointment for Clinic A
    lead_a = Lead(clinic_id=clinic_a.id, full_name="Fatima Ali", phone="+923001234567", source="whatsapp", status="new")
    db_session.add(lead_a)
    db_session.flush()

    appt_a = Appointment(
        clinic_id=clinic_a.id,
        lead_id=lead_a.id,
        title="Dental Scaling",
        scheduled_at=datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc),
        duration_minutes=45,
        timezone="Asia/Karachi",
        status="confirmed",
        calendar_sync_status="pending",
    )
    db_session.add(appt_a)
    db_session.commit()

    return {
        "clinic_a": clinic_a,
        "user_a": user_a,
        "token_a": create_access_token(str(user_a.id)),
        "staff_a": staff_a,
        "token_staff_a": create_access_token(str(staff_a.id)),
        "clinic_b": clinic_b,
        "user_b": user_b,
        "token_b": create_access_token(str(user_b.id)),
        "unauth_token": create_access_token(str(unauth_user.id)),
        "lead_a": lead_a,
        "appt_a": appt_a,
    }


# ============================================================================
# 1-3. Authentication & Authorization Tests
# ============================================================================

def test_1_unauthenticated_calendar_endpoint_rejected(client):
    res = client.get("/api/v1/calendar/connections")
    assert res.status_code == 401


def test_2_missing_x_clinic_id_rejected(client, setup_tenants):
    token = setup_tenants["token_a"]
    res = client.get("/api/v1/calendar/connections", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400
    assert "Missing required header" in res.text


def test_3_unauthorized_role_rejected_where_applicable(client, setup_tenants):
    unauth_token = setup_tenants["unauth_token"]
    clinic_a_id = str(setup_tenants["clinic_a"].id)
    res = client.get(
        "/api/v1/calendar/connections",
        headers={"Authorization": f"Bearer {unauth_token}", "X-Clinic-ID": clinic_a_id},
    )
    assert res.status_code == 403


# ============================================================================
# 4-6. Tenant Isolation Tests
# ============================================================================

def test_4_clinic_a_cannot_access_clinic_b_calendar_connection(client, db_session, setup_tenants):
    clinic_b = setup_tenants["clinic_b"]
    token_a = setup_tenants["token_a"]

    # Add connection for Clinic B
    conn_b = CalendarConnection(
        clinic_id=clinic_b.id,
        provider="google",
        account_identifier="drzaid@gmail.com",
        encrypted_access_token=encrypt_token("b_access_token"),
        encrypted_refresh_token=encrypt_token("b_refresh_token"),
        status="connected",
    )
    db_session.add(conn_b)
    db_session.commit()

    # User A requests Clinic A connections
    res = client.get(
        "/api/v1/calendar/connections",
        headers={"Authorization": f"Bearer {token_a}", "X-Clinic-ID": str(setup_tenants["clinic_a"].id)},
    )
    assert res.status_code == 200
    connections = res.json()
    assert len(connections) == 0  # Cannot see Clinic B's connection


def test_5_clinic_a_cannot_access_clinic_b_calendar_list(client, setup_tenants):
    token_a = setup_tenants["token_a"]
    clinic_b_id = str(setup_tenants["clinic_b"].id)

    # User A tries to pass Clinic B ID in header
    res = client.get(
        "/api/v1/calendar/calendars?provider=google",
        headers={"Authorization": f"Bearer {token_a}", "X-Clinic-ID": clinic_b_id},
    )
    assert res.status_code == 403


def test_6_clinic_a_cannot_synchronize_clinic_b_appointments(db_session, setup_tenants):
    clinic_b = setup_tenants["clinic_b"]
    appt_b = Appointment(
        clinic_id=clinic_b.id,
        title="Clinic B Scaling",
        scheduled_at=datetime(2026, 9, 11, 14, 0, tzinfo=timezone.utc),
        duration_minutes=30,
        status="confirmed",
        calendar_sync_status="pending",
    )
    db_session.add(appt_b)
    db_session.commit()

    # Clinic A has a mock connection
    conn_a = CalendarConnection(
        clinic_id=setup_tenants["clinic_a"].id,
        provider="google",
        encrypted_access_token=encrypt_token("a_token"),
        status="connected",
    )
    db_session.add(conn_a)
    db_session.commit()

    # Syncing Clinic A must not touch Clinic B's appointment
    assert appt_b.clinic_id == clinic_b.id
    assert appt_b.calendar_connection_id is None


# ============================================================================
# 7-11. OAuth State, CSRF, and Security Tests
# ============================================================================

def test_7_oauth_state_is_generated(client, setup_tenants):
    token_a = setup_tenants["token_a"]
    clinic_a_id = str(setup_tenants["clinic_a"].id)

    res = client.post(
        "/api/v1/calendar/google/connect",
        headers={"Authorization": f"Bearer {token_a}", "X-Clinic-ID": clinic_a_id},
    )
    assert res.status_code == 200
    data = res.json()
    assert "authorization_url" in data
    assert "state=" in data["authorization_url"]
    assert "client_id=" in data["authorization_url"]


def test_8_invalid_oauth_state_is_rejected(client):
    res = client.get("/api/v1/calendar/google/callback?code=test_code&state=tampered_invalid_state")
    assert res.status_code == 400
    assert "Invalid OAuth state" in res.text


def test_9_expired_oauth_state_is_rejected():
    clinic_id = uuid.uuid4()
    user_id = uuid.uuid4()
    # Generate expired state (-1 minute)
    expired_state = generate_oauth_state(clinic_id, user_id, "google", expires_minutes=-1)
    with pytest.raises(Exception) as exc:
        verify_oauth_state(expired_state, "google")
    assert "expired" in str(exc.value).lower()


def test_10_callback_cannot_arbitrarily_select_another_clinic(client, db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    user_a = setup_tenants["user_a"]
    clinic_b = setup_tenants["clinic_b"]

    # State is securely signed with Clinic A ID
    state = generate_oauth_state(clinic_a.id, user_a.id, "google")

    mock_exchange = {
        "access_token": "mock_google_access",
        "refresh_token": "mock_google_refresh",
        "token_expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "account_identifier": "clinic_a@gmail.com",
    }

    with patch("app.integrations.calendar.google.GoogleCalendarProvider.exchange_code", new_callable=AsyncMock, return_value=mock_exchange):
        res = client.get(f"/api/v1/calendar/google/callback?code=valid_code&state={state}")
        assert res.status_code == 200

    # Connection MUST be attached to Clinic A, never Clinic B
    conn_a = db_session.scalar(select(CalendarConnection).where(CalendarConnection.clinic_id == clinic_a.id))
    conn_b = db_session.scalar(select(CalendarConnection).where(CalendarConnection.clinic_id == clinic_b.id))
    assert conn_a is not None
    assert conn_a.account_identifier == "clinic_a@gmail.com"
    assert conn_b is None


def test_11_tokens_are_not_returned_in_api_responses(client, db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    token_a = setup_tenants["token_a"]

    conn = CalendarConnection(
        clinic_id=clinic_a.id,
        provider="google",
        account_identifier="secure@gmail.com",
        encrypted_access_token=encrypt_token("SECRET_ACCESS_TOKEN_XYZ"),
        encrypted_refresh_token=encrypt_token("SECRET_REFRESH_TOKEN_123"),
        status="connected",
    )
    db_session.add(conn)
    db_session.commit()

    res = client.get(
        "/api/v1/calendar/connections",
        headers={"Authorization": f"Bearer {token_a}", "X-Clinic-ID": str(clinic_a.id)},
    )
    assert res.status_code == 200
    res_text = json.dumps(res.json())
    assert "SECRET_ACCESS_TOKEN_XYZ" not in res_text
    assert "SECRET_REFRESH_TOKEN_123" not in res_text
    assert "encrypted_access_token" not in res_text
    assert "encrypted_refresh_token" not in res_text


# ============================================================================
# 12-15. Connection Management & Disconnect Tests
# ============================================================================

@pytest.mark.anyio
async def test_12_provider_connection_can_be_created(db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    user_a = setup_tenants["user_a"]
    state = generate_oauth_state(clinic_a.id, user_a.id, "google")

    mock_exchange = {
        "access_token": "mock_acc_123",
        "refresh_token": "mock_ref_123",
        "token_expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "account_identifier": "clinic_owner@gmail.com",
    }
    with patch("app.integrations.calendar.google.GoogleCalendarProvider.exchange_code", new_callable=AsyncMock, return_value=mock_exchange):
        conn = await calendar_service.handle_oauth_callback(
            db=db_session,
            provider_name="google",
            code="test_code",
            state=state,
        )
        assert conn.status == "connected"
        assert conn.account_identifier == "clinic_owner@gmail.com"
        assert decrypt_token(conn.encrypted_access_token) == "mock_acc_123"


def test_13_provider_connection_status_is_returned_safely(client, db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    token_a = setup_tenants["token_a"]

    conn = CalendarConnection(
        clinic_id=clinic_a.id,
        provider="microsoft",
        account_identifier="admin@outlook.com",
        encrypted_access_token=encrypt_token("token"),
        status="connected",
        calendar_name="Dental Schedule",
    )
    db_session.add(conn)
    db_session.commit()

    res = client.get(
        "/api/v1/calendar/connections",
        headers={"Authorization": f"Bearer {token_a}", "X-Clinic-ID": str(clinic_a.id)},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["provider"] == "microsoft"
    assert data[0]["status"] == "connected"
    assert data[0]["account_identifier"] == "admin@outlook.com"
    assert data[0]["calendar_name"] == "Dental Schedule"


def test_14_disconnect_removes_and_invalidates_credentials(client, db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    token_a = setup_tenants["token_a"]

    conn = CalendarConnection(
        clinic_id=clinic_a.id,
        provider="google",
        account_identifier="tariq@gmail.com",
        encrypted_access_token=encrypt_token("live_token"),
        encrypted_refresh_token=encrypt_token("live_refresh"),
        status="connected",
    )
    db_session.add(conn)
    db_session.commit()

    res = client.post(
        "/api/v1/calendar/google/disconnect",
        headers={"Authorization": f"Bearer {token_a}", "X-Clinic-ID": str(clinic_a.id)},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "disconnected"

    # Verify credentials removed from DB
    db_session.refresh(conn)
    assert conn.status == "disconnected"
    assert conn.encrypted_access_token == ""
    assert conn.encrypted_refresh_token is None


@pytest.mark.anyio
async def test_15_disconnected_provider_cannot_synchronize(db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    appt = setup_tenants["appt_a"]

    conn = CalendarConnection(
        clinic_id=clinic_a.id,
        provider="google",
        encrypted_access_token="",
        status="disconnected",
    )
    db_session.add(conn)
    db_session.commit()

    await calendar_service.sync_appointment(db_session, appt)
    assert appt.calendar_sync_status == "disconnected"
    assert appt.external_event_id is None


# ============================================================================
# 16-20. Appointment -> Calendar Event Synchronization Tests
# ============================================================================

@pytest.mark.anyio
async def test_16_eligible_appointment_creates_external_event(db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    appt = setup_tenants["appt_a"]

    conn = CalendarConnection(
        clinic_id=clinic_a.id,
        provider="google",
        calendar_identifier="primary",
        encrypted_access_token=encrypt_token("valid_access_token"),
        status="connected",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(conn)
    db_session.commit()

    with patch("app.integrations.calendar.google.GoogleCalendarProvider.create_event", new_callable=AsyncMock, return_value="google_evt_999") as mock_create:
        await calendar_service.sync_appointment(db_session, appt)

        assert mock_create.called
        assert appt.calendar_sync_status == "synced"
        assert appt.external_event_id == "google_evt_999"
        assert appt.calendar_last_synced_at is not None


@pytest.mark.anyio
async def test_17_existing_event_is_updated_instead_of_duplicated(db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    appt = setup_tenants["appt_a"]
    appt.external_event_id = "existing_google_evt_123"

    conn = CalendarConnection(
        clinic_id=clinic_a.id,
        provider="google",
        encrypted_access_token=encrypt_token("valid_token"),
        status="connected",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(conn)
    db_session.commit()

    with patch("app.integrations.calendar.google.GoogleCalendarProvider.update_event", new_callable=AsyncMock) as mock_update, \
         patch("app.integrations.calendar.google.GoogleCalendarProvider.create_event", new_callable=AsyncMock) as mock_create:
        await calendar_service.sync_appointment(db_session, appt)

        assert mock_update.called
        assert not mock_create.called  # Did not create a duplicate event
        assert appt.external_event_id == "existing_google_evt_123"
        assert appt.calendar_sync_status == "synced"


@pytest.mark.anyio
async def test_18_appointment_cancellation_removes_external_event(db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    appt = setup_tenants["appt_a"]
    appt.status = "cancelled"
    appt.external_event_id = "event_to_delete_456"

    conn = CalendarConnection(
        clinic_id=clinic_a.id,
        provider="google",
        encrypted_access_token=encrypt_token("valid_token"),
        status="connected",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(conn)
    db_session.commit()

    with patch("app.integrations.calendar.google.GoogleCalendarProvider.delete_event", new_callable=AsyncMock) as mock_delete:
        await calendar_service.sync_appointment(db_session, appt)

        assert mock_delete.called
        assert appt.external_event_id is None  # Event ID cleared
        assert appt.calendar_sync_status == "synced"


@pytest.mark.anyio
async def test_19_appointment_rescheduling_updates_external_event(db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    appt = setup_tenants["appt_a"]
    appt.external_event_id = "rescheduled_evt_789"
    appt.scheduled_at = datetime(2026, 9, 12, 16, 0, tzinfo=timezone.utc)

    conn = CalendarConnection(
        clinic_id=clinic_a.id,
        provider="microsoft",
        encrypted_access_token=encrypt_token("ms_token"),
        status="connected",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(conn)
    db_session.commit()

    with patch("app.integrations.calendar.microsoft.MicrosoftCalendarProvider.update_event", new_callable=AsyncMock) as mock_ms_update:
        await calendar_service.sync_appointment(db_session, appt)

        assert mock_ms_update.called
        call_args = mock_ms_update.call_args[1]
        assert "2026-09-12T16:00:00" in call_args["event_data"]["start_time"]
        assert appt.calendar_sync_status == "synced"


@pytest.mark.anyio
async def test_20_synchronization_is_idempotent(db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    appt = setup_tenants["appt_a"]

    conn = CalendarConnection(
        clinic_id=clinic_a.id,
        provider="google",
        encrypted_access_token=encrypt_token("valid_token"),
        status="connected",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(conn)
    db_session.commit()

    # First run creates event
    with patch("app.integrations.calendar.google.GoogleCalendarProvider.create_event", new_callable=AsyncMock, return_value="google_evt_single"):
        await calendar_service.sync_appointment(db_session, appt)
        assert appt.external_event_id == "google_evt_single"

    # Second run updates same event
    with patch("app.integrations.calendar.google.GoogleCalendarProvider.update_event", new_callable=AsyncMock) as mock_update, \
         patch("app.integrations.calendar.google.GoogleCalendarProvider.create_event", new_callable=AsyncMock) as mock_create:
        await calendar_service.sync_appointment(db_session, appt)
        assert mock_update.called
        assert not mock_create.called
        assert appt.external_event_id == "google_evt_single"


# ============================================================================
# 21-23. Token Refresh Tests
# ============================================================================

@pytest.mark.anyio
async def test_21_expired_token_triggers_refresh(db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    conn = CalendarConnection(
        clinic_id=clinic_a.id,
        provider="google",
        encrypted_access_token=encrypt_token("expired_access_token"),
        encrypted_refresh_token=encrypt_token("valid_refresh_token"),
        token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        status="connected",
    )
    db_session.add(conn)
    db_session.commit()

    mock_refresh_res = {
        "access_token": "fresh_new_access_token_123",
        "refresh_token": "valid_refresh_token",
        "token_expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
    }

    with patch("app.integrations.calendar.google.GoogleCalendarProvider.refresh_tokens", new_callable=AsyncMock, return_value=mock_refresh_res) as mock_refresh:
        token = await calendar_service._ensure_valid_token(db_session, conn)
        assert mock_refresh.called
        assert token == "fresh_new_access_token_123"


@pytest.mark.anyio
async def test_22_successful_refresh_updates_stored_credentials(db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    conn = CalendarConnection(
        clinic_id=clinic_a.id,
        provider="google",
        encrypted_access_token=encrypt_token("old_token"),
        encrypted_refresh_token=encrypt_token("valid_refresh"),
        token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        status="connected",
    )
    db_session.add(conn)
    db_session.commit()

    mock_res = {
        "access_token": "new_persisted_token_999",
        "refresh_token": "new_refresh_token_888",
        "token_expires_at": datetime.now(timezone.utc) + timedelta(hours=2),
    }

    with patch("app.integrations.calendar.google.GoogleCalendarProvider.refresh_tokens", new_callable=AsyncMock, return_value=mock_res):
        await calendar_service._ensure_valid_token(db_session, conn)

    db_session.refresh(conn)
    assert decrypt_token(conn.encrypted_access_token) == "new_persisted_token_999"
    assert decrypt_token(conn.encrypted_refresh_token) == "new_refresh_token_888"
    assert conn.status == "connected"


@pytest.mark.anyio
async def test_23_failed_refresh_marks_connection_appropriately(db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    conn = CalendarConnection(
        clinic_id=clinic_a.id,
        provider="google",
        encrypted_access_token=encrypt_token("expired_token"),
        encrypted_refresh_token=encrypt_token("revoked_refresh"),
        token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        status="connected",
    )
    db_session.add(conn)
    db_session.commit()

    with patch("app.integrations.calendar.google.GoogleCalendarProvider.refresh_tokens", side_effect=CalendarAuthError("Token revoked", provider="google")):
        with pytest.raises(CalendarAuthError):
            await calendar_service._ensure_valid_token(db_session, conn)

    db_session.refresh(conn)
    assert conn.status == "expired"
    assert "Token revoked" in conn.last_error


# ============================================================================
# 24-26. Failure, Retry & Rate Limiting Tests
# ============================================================================

@pytest.mark.anyio
async def test_24_temporary_provider_failure_retries(db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    appt = setup_tenants["appt_a"]

    conn = CalendarConnection(
        clinic_id=clinic_a.id,
        provider="google",
        encrypted_access_token=encrypt_token("valid_token"),
        status="connected",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(conn)
    db_session.commit()

    with patch("app.integrations.calendar.google.GoogleCalendarProvider.create_event", side_effect=CalendarProviderError("Temporary 503 Outage", provider="google", retryable=True)):
        await calendar_service.sync_appointment(db_session, appt)

        assert appt.calendar_retry_count == 1
        assert appt.calendar_sync_status == "pending"  # Kept pending for background retry
        assert "Temporary 503" in appt.calendar_sync_error


@pytest.mark.anyio
async def test_25_permanent_provider_failure_does_not_retry_indefinitely(db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    appt = setup_tenants["appt_a"]

    conn = CalendarConnection(
        clinic_id=clinic_a.id,
        provider="google",
        encrypted_access_token=encrypt_token("valid_token"),
        status="connected",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(conn)
    db_session.commit()

    with patch("app.integrations.calendar.google.GoogleCalendarProvider.create_event", side_effect=CalendarAuthError("Invalid credentials", provider="google")):
        await calendar_service.sync_appointment(db_session, appt)

        assert appt.calendar_sync_status == "failed"  # Marked failed immediately


@pytest.mark.anyio
async def test_26_provider_rate_limiting_is_handled_safely(db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    appt = setup_tenants["appt_a"]

    conn = CalendarConnection(
        clinic_id=clinic_a.id,
        provider="google",
        encrypted_access_token=encrypt_token("valid_token"),
        status="connected",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(conn)
    db_session.commit()

    with patch("app.integrations.calendar.google.GoogleCalendarProvider.create_event", side_effect=CalendarRateLimitError("Rate limit reached", provider="google")):
        await calendar_service.sync_appointment(db_session, appt)

        assert appt.calendar_retry_count == 1
        assert appt.calendar_sync_status == "pending"


# ============================================================================
# 27-28. Timezone Tests
# ============================================================================

@pytest.mark.anyio
async def test_27_calendar_event_uses_clinic_timezone(db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    appt = setup_tenants["appt_a"]
    appt.timezone = "Asia/Karachi"

    conn = CalendarConnection(
        clinic_id=clinic_a.id,
        provider="google",
        encrypted_access_token=encrypt_token("token"),
        status="connected",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(conn)
    db_session.commit()

    with patch("app.integrations.calendar.google.GoogleCalendarProvider.create_event", new_callable=AsyncMock, return_value="evt_tz_123") as mock_create:
        await calendar_service.sync_appointment(db_session, appt)

        assert mock_create.called
        event_data = mock_create.call_args[1]["event_data"]
        assert event_data["timezone"] == "Asia/Karachi"


@pytest.mark.anyio
async def test_28_appointment_synchronization_preserves_correct_start_end_time(db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    appt = setup_tenants["appt_a"]
    appt.scheduled_at = datetime(2026, 9, 15, 9, 30, tzinfo=timezone.utc)
    appt.duration_minutes = 60

    conn = CalendarConnection(
        clinic_id=clinic_a.id,
        provider="google",
        encrypted_access_token=encrypt_token("token"),
        status="connected",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(conn)
    db_session.commit()

    with patch("app.integrations.calendar.google.GoogleCalendarProvider.create_event", new_callable=AsyncMock, return_value="evt_time_123") as mock_create:
        await calendar_service.sync_appointment(db_session, appt)

        event_data = mock_create.call_args[1]["event_data"]
        assert "2026-09-15T09:30:00" in event_data["start_time"]
        assert "2026-09-15T10:30:00" in event_data["end_time"]


# ============================================================================
# 29-32. Privacy & Security Tests
# ============================================================================

def test_29_api_responses_never_contain_access_tokens(client, db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    token_a = setup_tenants["token_a"]

    conn = CalendarConnection(
        clinic_id=clinic_a.id,
        provider="google",
        account_identifier="safe_test@gmail.com",
        encrypted_access_token=encrypt_token("UNSAFE_ACCESS_12345"),
        status="connected",
    )
    db_session.add(conn)
    db_session.commit()

    res = client.get(
        "/api/v1/calendar/connections",
        headers={"Authorization": f"Bearer {token_a}", "X-Clinic-ID": str(clinic_a.id)},
    )
    assert res.status_code == 200
    content = res.text
    assert "UNSAFE_ACCESS_12345" not in content


def test_30_api_responses_never_contain_refresh_tokens(client, db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    token_a = setup_tenants["token_a"]

    conn = CalendarConnection(
        clinic_id=clinic_a.id,
        provider="google",
        account_identifier="safe_test@gmail.com",
        encrypted_access_token=encrypt_token("access"),
        encrypted_refresh_token=encrypt_token("UNSAFE_REFRESH_99999"),
        status="connected",
    )
    db_session.add(conn)
    db_session.commit()

    res = client.get(
        "/api/v1/calendar/connections",
        headers={"Authorization": f"Bearer {token_a}", "X-Clinic-ID": str(clinic_a.id)},
    )
    assert res.status_code == 200
    content = res.text
    assert "UNSAFE_REFRESH_99999" not in content


def test_31_logs_do_not_expose_oauth_secrets(caplog, db_session, setup_tenants):
    clinic_a = setup_tenants["clinic_a"]
    user_a = setup_tenants["user_a"]

    with caplog.at_level("INFO"):
        auth_url = calendar_service.initiate_oauth(clinic_a.id, user_a.id, "google")
        assert auth_url is not None
        for record in caplog.records:
            assert "client_secret" not in record.message.lower()
            assert "access_token" not in record.message.lower()


def test_32_calendar_descriptions_do_not_contain_prohibited_internal_data(setup_tenants):
    appt = setup_tenants["appt_a"]
    appt.description = "Routine dental scaling"
    event_data = calendar_service._build_event_payload(appt)

    desc = event_data["description"]
    # Must contain patient and title
    assert "Patient: Fatima Ali" in desc
    assert "Dental Scaling" in desc

    # Must NOT contain internal system prompts, conversation dumps, or passwords
    assert "SYSTEM INSTRUCTION" not in desc
    assert "password" not in desc.lower()
    assert "bearer" not in desc.lower()
    assert "api_key" not in desc.lower()

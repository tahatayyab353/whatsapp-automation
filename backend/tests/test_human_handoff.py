import json
import uuid
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.exceptions import AIProviderTimeoutError
from app.ai.types import AIResponse
from app.core.security import create_access_token
from app.db.database import get_db
from app.integrations.whatsapp.security import generate_webhook_signature
from app.main import app
from app.models import (
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
from app.schemas.whatsapp_message import WhatsAppMessageItem, WhatsAppSendMessageResponse
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
def setup_handoff_data(db_session):
    # Clinic A
    clinic_a = Clinic(name="Karachi Dental Studio", slug="karachi-dental", timezone="Asia/Karachi")
    staff_a = User(email="staff@kds.pk", full_name="Ali Staff", is_active=True)
    owner_a = User(email="owner@kds.pk", full_name="Dr. Tariq", is_active=True)
    db_session.add_all([clinic_a, staff_a, owner_a])
    db_session.commit()

    db_session.add(ClinicMembership(clinic_id=clinic_a.id, user_id=staff_a.id, role="staff"))
    db_session.add(ClinicMembership(clinic_id=clinic_a.id, user_id=owner_a.id, role="owner"))

    whatsapp_a = WhatsAppAccount(
        clinic_id=clinic_a.id,
        phone_number="+923001234567",
        phone_number_id="phone_id_clinic_a",
        business_account_id="waba_id_clinic_a",
        display_name="Karachi Dental Official",
        access_token="clinic_a_secret_token",
        is_active=True,
    )
    lead_a = Lead(
        clinic_id=clinic_a.id,
        full_name="Farhan Qureshi",
        phone="+923005554433",
        source="whatsapp",
        status="new",
    )
    db_session.add_all([whatsapp_a, lead_a])
    db_session.commit()

    conv_a = Conversation(
        clinic_id=clinic_a.id,
        lead_id=lead_a.id,
        channel="whatsapp",
        status="open",
    )
    db_session.add(conv_a)
    db_session.commit()

    # Clinic B
    clinic_b = Clinic(name="Lahore Aesthetic Clinic", slug="lahore-aesthetic", timezone="Asia/Karachi")
    staff_b = User(email="staff@lahore.pk", full_name="Usman Staff", is_active=True)
    db_session.add_all([clinic_b, staff_b])
    db_session.commit()

    db_session.add(ClinicMembership(clinic_id=clinic_b.id, user_id=staff_b.id, role="staff"))
    whatsapp_b = WhatsAppAccount(
        clinic_id=clinic_b.id,
        phone_number="+923219876543",
        phone_number_id="phone_id_clinic_b",
        display_name="Lahore Aesthetic Official",
        access_token="clinic_b_secret_token",
        is_active=True,
    )
    lead_b = Lead(
        clinic_id=clinic_b.id,
        full_name="Babar Azam",
        phone="+923211112233",
        source="whatsapp",
        status="new",
    )
    db_session.add_all([whatsapp_b, lead_b])
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
        "staff_a": staff_a,
        "owner_a": owner_a,
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


def make_webhook_payload(phone_number_id: str, from_phone: str, msg_id: str, text: str) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_123",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+923001234567",
                                "phone_number_id": phone_number_id,
                            },
                            "contacts": [{"profile": {"name": from_phone}, "wa_id": from_phone.lstrip("+")}],
                            "messages": [
                                {
                                    "from": from_phone,
                                    "id": msg_id,
                                    "timestamp": "1725177600",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


# ============================================================================
# CHUNK 8 Tests: Human Handoff & Escalation
# ============================================================================


def test_customer_requesting_human_creates_handoff(client, db_session, setup_handoff_data):
    clinic_a = setup_handoff_data["clinic_a"]
    app_secret = "meta_test_secret"

    payload = make_webhook_payload(
        phone_number_id="phone_id_clinic_a",
        from_phone="923005554433",
        msg_id="wamid.MSG_HUMAN_REQ",
        text="I want to speak to a human receptionist please",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.return_value = AIResponse(
            content="Sure! I'll connect you with our front-desk team.",
            provider="gemini",
            model="gemini-1.5-flash",
        )
        mock_send.return_value = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.OUT_HANDOFF")])

        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200

    # Verify Handoff created
    handoff = db_session.scalar(select(Handoff).where(Handoff.clinic_id == clinic_a.id))
    assert handoff is not None
    assert handoff.status == "pending"
    assert handoff.reason == "customer_requested_human"


def test_ai_can_trigger_handoff_on_uncertainty(client, db_session, setup_handoff_data):
    clinic_a = setup_handoff_data["clinic_a"]
    app_secret = "meta_test_secret"

    payload = make_webhook_payload(
        phone_number_id="phone_id_clinic_a",
        from_phone="923005554433",
        msg_id="wamid.MSG_AI_UNCERTAIN",
        text="Can you explain rare insurance reimbursement rules?",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.return_value = AIResponse(
            content="I do not have those details. I will connect you with our team right away.",
            provider="gemini",
            model="gemini-1.5-flash",
        )
        mock_send.return_value = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.OUT_UNCERTAIN")])

        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200

    handoff = db_session.scalar(select(Handoff).where(Handoff.clinic_id == clinic_a.id))
    assert handoff is not None
    assert handoff.status == "pending"
    assert handoff.reason == "ai_uncertain"


def test_handoff_reason_is_persisted(db_session, setup_handoff_data):
    clinic_a = setup_handoff_data["clinic_a"]
    conv_a = setup_handoff_data["conv_a"]

    handoff = handoff_service.request_handoff(
        db=db_session,
        clinic_id=clinic_a.id,
        conversation_id=conv_a.id,
        reason="billing_issue",
        notes="Customer disputed invoice",
    )
    assert handoff.id is not None
    assert handoff.reason == "billing_issue"
    assert handoff.notes == "Customer disputed invoice"
    assert handoff.status == "pending"


def test_existing_active_handoff_is_reused(db_session, setup_handoff_data):
    clinic_a = setup_handoff_data["clinic_a"]
    conv_a = setup_handoff_data["conv_a"]

    h1 = handoff_service.request_handoff(
        db=db_session,
        clinic_id=clinic_a.id,
        conversation_id=conv_a.id,
        reason="complaint",
    )
    h2 = handoff_service.request_handoff(
        db=db_session,
        clinic_id=clinic_a.id,
        conversation_id=conv_a.id,
        reason="urgent_request",
    )

    assert h1.id == h2.id
    all_handoffs = db_session.scalars(select(Handoff).where(Handoff.clinic_id == clinic_a.id)).all()
    assert len(all_handoffs) == 1


def test_ai_does_not_reply_when_human_active(client, db_session, setup_handoff_data):
    clinic_a = setup_handoff_data["clinic_a"]
    staff_a = setup_handoff_data["staff_a"]
    conv_a = setup_handoff_data["conv_a"]
    app_secret = "meta_test_secret"

    # Human staff assigns conversation
    handoff = handoff_service.request_handoff(
        db=db_session,
        clinic_id=clinic_a.id,
        conversation_id=conv_a.id,
        reason="customer_requested_human",
    )
    handoff_service.assign_handoff(
        db=db_session,
        clinic_id=clinic_a.id,
        handoff_id=handoff.id,
        user_id=staff_a.id,
    )

    # Customer sends follow-up message
    payload = make_webhook_payload(
        phone_number_id="phone_id_clinic_a",
        from_phone="923005554433",
        msg_id="wamid.MSG_HUMAN_ACTIVE",
        text="Are you still there?",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200

        # AI was NEVER called because human is active
        assert mock_gemini.await_count == 0
        assert mock_send.await_count == 0


def test_ai_response_is_discarded_if_human_claims_conversation(db_session, setup_handoff_data):
    clinic_a = setup_handoff_data["clinic_a"]
    staff_a = setup_handoff_data["staff_a"]
    conv_a = setup_handoff_data["conv_a"]

    # Request handoff
    handoff = handoff_service.request_handoff(
        db=db_session,
        clinic_id=clinic_a.id,
        conversation_id=conv_a.id,
        reason="customer_requested_human",
    )

    # Staff claims the conversation
    handoff_service.assign_handoff(
        db=db_session,
        clinic_id=clinic_a.id,
        handoff_id=handoff.id,
        user_id=staff_a.id,
    )

    with (
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.return_value = AIResponse(content="Delayed AI reply", provider="gemini", model="gemini-1.5-flash")

        from app.services.whatsapp_ai_service import whatsapp_ai_service
        res = None
        import anyio
        async def run_ai():
            return await whatsapp_ai_service.process_and_reply_customer_message(
                db=db_session,
                clinic_id=clinic_a.id,
                conversation_id=conv_a.id,
                customer_message="Help",
                customer_phone="+923005554433",
            )
        res = anyio.run(run_ai)
        assert res is None
        assert mock_send.await_count == 0


def test_authorized_staff_can_claim_handoff(client, db_session, setup_handoff_data):
    clinic_a = setup_handoff_data["clinic_a"]
    staff_a = setup_handoff_data["staff_a"]
    conv_a = setup_handoff_data["conv_a"]

    handoff = handoff_service.request_handoff(
        db=db_session,
        clinic_id=clinic_a.id,
        conversation_id=conv_a.id,
        reason="customer_requested_human",
    )

    headers = auth_headers(staff_a, clinic_a)
    res = client.post(f"/api/v1/whatsapp/handoffs/{handoff.id}/assign", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "assigned"
    assert data["assigned_to_user_id"] == str(staff_a.id)


def test_unauthorized_user_cannot_claim_handoff(client, db_session, setup_handoff_data):
    clinic_a = setup_handoff_data["clinic_a"]
    conv_a = setup_handoff_data["conv_a"]

    handoff = handoff_service.request_handoff(
        db=db_session,
        clinic_id=clinic_a.id,
        conversation_id=conv_a.id,
        reason="customer_requested_human",
    )

    # Missing authorization header
    res = client.post(f"/api/v1/whatsapp/handoffs/{handoff.id}/assign")
    assert res.status_code == 401


def test_staff_can_resolve_handoff(client, db_session, setup_handoff_data):
    clinic_a = setup_handoff_data["clinic_a"]
    staff_a = setup_handoff_data["staff_a"]
    conv_a = setup_handoff_data["conv_a"]

    handoff = handoff_service.request_handoff(
        db=db_session,
        clinic_id=clinic_a.id,
        conversation_id=conv_a.id,
        reason="customer_requested_human",
    )
    handoff_service.assign_handoff(db=db_session, clinic_id=clinic_a.id, handoff_id=handoff.id, user_id=staff_a.id)

    headers = auth_headers(staff_a, clinic_a)
    res = client.post(
        f"/api/v1/whatsapp/handoffs/{handoff.id}/resolve",
        headers=headers,
        json={"notes": "Resolved with appointment booked on phone"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "resolved"

    db_session.refresh(conv_a)
    assert conv_a.status == "open"


def test_invalid_handoff_transition_is_rejected(client, db_session, setup_handoff_data):
    clinic_a = setup_handoff_data["clinic_a"]
    staff_a = setup_handoff_data["staff_a"]
    conv_a = setup_handoff_data["conv_a"]

    handoff = handoff_service.request_handoff(
        db=db_session,
        clinic_id=clinic_a.id,
        conversation_id=conv_a.id,
        reason="customer_requested_human",
    )
    handoff_service.resolve_handoff(db=db_session, clinic_id=clinic_a.id, handoff_id=handoff.id)

    headers = auth_headers(staff_a, clinic_a)
    # Attempting to assign an already resolved handoff
    res = client.post(f"/api/v1/whatsapp/handoffs/{handoff.id}/assign", headers=headers)
    assert res.status_code == 400


def test_clinic_a_cannot_access_clinic_b_handoff(client, db_session, setup_handoff_data):
    clinic_a = setup_handoff_data["clinic_a"]
    staff_a = setup_handoff_data["staff_a"]
    clinic_b = setup_handoff_data["clinic_b"]
    conv_b = setup_handoff_data["conv_b"]

    # Handoff in Clinic B
    handoff_b = handoff_service.request_handoff(
        db=db_session,
        clinic_id=clinic_b.id,
        conversation_id=conv_b.id,
        reason="customer_requested_human",
    )

    # Staff A tries to access Handoff B
    headers = auth_headers(staff_a, clinic_a)
    res = client.get(f"/api/v1/whatsapp/handoffs/{handoff_b.id}", headers=headers)
    assert res.status_code == 404


def test_staff_message_is_persisted_as_staff_message_and_sent_via_meta(client, db_session, setup_handoff_data):
    clinic_a = setup_handoff_data["clinic_a"]
    staff_a = setup_handoff_data["staff_a"]
    conv_a = setup_handoff_data["conv_a"]

    handoff = handoff_service.request_handoff(
        db=db_session,
        clinic_id=clinic_a.id,
        conversation_id=conv_a.id,
        reason="customer_requested_human",
    )
    handoff_service.assign_handoff(db=db_session, clinic_id=clinic_a.id, handoff_id=handoff.id, user_id=staff_a.id)

    headers = auth_headers(staff_a, clinic_a)
    mock_meta_resp = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.STAFF_OUT_999")])

    with patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = mock_meta_resp

        res = client.post(
            f"/api/v1/whatsapp/handoffs/{handoff.id}/messages",
            headers=headers,
            json={"content": "Hello! I am Dr. Tariq's receptionist. How can I help you today?"},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["sender_type"] == "staff"
        assert data["content"] == "Hello! I am Dr. Tariq's receptionist. How can I help you today?"
        assert data["external_message_id"] == "wamid.STAFF_OUT_999"

        # Verify WhatsApp client was invoked
        assert mock_send.await_count == 1
        assert mock_send.call_args[1]["recipient_phone"] == "+923005554433"


def test_handoff_api_never_exposes_credentials(client, db_session, setup_handoff_data):
    clinic_a = setup_handoff_data["clinic_a"]
    staff_a = setup_handoff_data["staff_a"]
    conv_a = setup_handoff_data["conv_a"]

    handoff = handoff_service.request_handoff(
        db=db_session,
        clinic_id=clinic_a.id,
        conversation_id=conv_a.id,
        reason="billing_issue",
    )

    headers = auth_headers(staff_a, clinic_a)
    res = client.get(f"/api/v1/whatsapp/handoffs/{handoff.id}", headers=headers)
    assert res.status_code == 200
    assert "clinic_a_secret_token" not in res.text
    assert "access_token" not in res.text


def test_complaint_can_trigger_handoff(client, db_session, setup_handoff_data):
    clinic_a = setup_handoff_data["clinic_a"]
    app_secret = "meta_test_secret"

    payload = make_webhook_payload(
        phone_number_id="phone_id_clinic_a",
        from_phone="923005554433",
        msg_id="wamid.MSG_COMPLAINT",
        text="I am very unhappy with this service and want to file a complaint!",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.return_value = AIResponse(
            content="I am so sorry to hear that. I am connecting you directly with our management team.",
            provider="gemini",
            model="gemini-1.5-flash",
        )
        mock_send.return_value = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.OUT_COMPLAINT")])

        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200

    handoff = db_session.scalar(select(Handoff).where(Handoff.clinic_id == clinic_a.id))
    assert handoff is not None
    assert handoff.reason == "complaint"


def test_explicit_human_request_triggers_handoff(client, db_session, setup_handoff_data):
    clinic_a = setup_handoff_data["clinic_a"]
    app_secret = "meta_test_secret"

    payload = make_webhook_payload(
        phone_number_id="phone_id_clinic_a",
        from_phone="923005554433",
        msg_id="wamid.MSG_EXP_HUMAN",
        text="Connect me to the receptionist",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.return_value = AIResponse(
            content="Connecting you with the receptionist now.",
            provider="gemini",
            model="gemini-1.5-flash",
        )
        mock_send.return_value = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.OUT_RECEPT")])

        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200

    handoff = db_session.scalar(select(Handoff).where(Handoff.clinic_id == clinic_a.id))
    assert handoff is not None
    assert handoff.reason == "customer_requested_human"

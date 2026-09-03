import json
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.exceptions import (
    AIAuthenticationError,
    AIProviderTimeoutError,
    AIRateLimitError,
    AITemporaryServerError,
)
from app.ai.types import AIResponse
from app.db.database import get_db
from app.integrations.whatsapp.client import WhatsAppClient
from app.integrations.whatsapp.exceptions import (
    WhatsAppAuthenticationError,
    WhatsAppRateLimitError,
)
from app.integrations.whatsapp.security import generate_webhook_signature
from app.main import app
from app.models import (
    Base,
    Clinic,
    ClinicMembership,
    Conversation,
    KnowledgeDocument,
    Lead,
    Message,
    User,
    WhatsAppAccount,
)
from app.schemas.whatsapp_message import WhatsAppMessageItem, WhatsAppSendMessageResponse


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
def setup_data(db_session):
    clinic_a = Clinic(name="Karachi Dental Studio", slug="karachi-dental", timezone="Asia/Karachi")
    owner_a = User(email="owner@kds.local", full_name="Dr. Tariq", is_active=True)
    db_session.add_all([clinic_a, owner_a])
    db_session.commit()

    db_session.add(ClinicMembership(clinic_id=clinic_a.id, user_id=owner_a.id, role="owner"))
    whatsapp_a = WhatsAppAccount(
        clinic_id=clinic_a.id,
        phone_number="+923001234567",
        phone_number_id="phone_id_clinic_a",
        business_account_id="waba_id_clinic_a",
        display_name="Karachi Dental Reception",
        access_token="clinic_a_secret_access_token",
        is_active=True,
    )
    knowledge_a = KnowledgeDocument(
        clinic_id=clinic_a.id,
        title="Scaling and Polishing Pricing",
        content="Scaling and polishing cost is PKR 4,500.",
        category="pricing",
        is_active=True,
    )

    # Clinic B
    clinic_b = Clinic(name="Lahore Aesthetic Clinic", slug="lahore-aesthetic", timezone="Asia/Karachi")
    db_session.add(clinic_b)
    db_session.commit()

    whatsapp_b = WhatsAppAccount(
        clinic_id=clinic_b.id,
        phone_number="+923219876543",
        phone_number_id="phone_id_clinic_b",
        display_name="Lahore Aesthetic Reception",
        access_token="clinic_b_secret_access_token",
        is_active=True,
    )
    knowledge_b = KnowledgeDocument(
        clinic_id=clinic_b.id,
        title="Hydrafacial Pricing",
        content="Hydrafacial cost is PKR 12,000.",
        category="pricing",
        is_active=True,
    )

    db_session.add_all([whatsapp_a, knowledge_a, whatsapp_b, knowledge_b])
    db_session.commit()

    return {
        "clinic_a": clinic_a,
        "whatsapp_a": whatsapp_a,
        "knowledge_a": knowledge_a,
        "clinic_b": clinic_b,
        "whatsapp_b": whatsapp_b,
        "knowledge_b": knowledge_b,
    }


def make_payload(phone_number_id: str, from_phone: str, msg_id: str, text: str, msg_type: str = "text") -> dict:
    msg_obj = {
        "from": from_phone,
        "id": msg_id,
        "timestamp": "1725177600",
        "type": msg_type,
    }
    if msg_type == "text":
        msg_obj["text"] = {"body": text}

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
                            "contacts": [{"profile": {"name": "Sara Ahmed"}, "wa_id": from_phone.lstrip("+")}],
                            "messages": [msg_obj],
                        },
                    }
                ],
            }
        ],
    }


# ============================================================================
# CHUNK 6D Tests: AI Receptionist + Outbound WhatsApp Pipeline
# ============================================================================


def test_gemini_primary_success_sends_whatsapp_and_persists_ai_message(client, db_session, setup_data):
    clinic_a = setup_data["clinic_a"]
    app_secret = "meta_test_secret_123"

    payload = make_payload(
        phone_number_id="phone_id_clinic_a",
        from_phone="923001112233",
        msg_id="wamid.INCOMING_001",
        text="How much is scaling and polishing?",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    mock_gemini_response = AIResponse(
        content="Scaling and polishing at Karachi Dental Studio costs PKR 4,500.",
        provider="gemini",
        model="gemini-1.5-flash",
    )
    mock_meta_response = WhatsAppSendMessageResponse(
        messaging_product="whatsapp",
        messages=[WhatsAppMessageItem(id="wamid.OUTBOUND_META_001")],
    )

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.ai.providers.groq.GroqProvider.generate", new_callable=AsyncMock) as mock_groq,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.return_value = mock_gemini_response
        mock_send.return_value = mock_meta_response

        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200

        # Verify Gemini called, Groq NOT called
        assert mock_gemini.await_count == 1
        assert mock_groq.await_count == 0

        # Verify Meta outbound send called with generated AI content
        assert mock_send.await_count == 1
        assert mock_send.call_args[1]["recipient_phone"] == "+923001112233"
        assert "PKR 4,500" in mock_send.call_args[1]["message"]

    # Verify Database State
    messages = db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id).order_by(Message.created_at)).all()
    assert len(messages) == 2

    # 1. Customer Message
    assert messages[0].sender_type == "customer"
    assert messages[0].content == "How much is scaling and polishing?"
    assert messages[0].external_message_id == "wamid.INCOMING_001"

    # 2. AI Message
    assert messages[1].sender_type == "ai"
    assert "PKR 4,500" in messages[1].content
    assert messages[1].external_message_id == "wamid.OUTBOUND_META_001"


def test_gemini_timeout_triggers_groq_fallback_and_outbound(client, db_session, setup_data):
    clinic_a = setup_data["clinic_a"]
    app_secret = "meta_test_secret_123"

    payload = make_payload(
        phone_number_id="phone_id_clinic_a",
        from_phone="923001112233",
        msg_id="wamid.INCOMING_TIMEOUT",
        text="What are your charges?",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    mock_groq_response = AIResponse(
        content="Our scaling and polishing is PKR 4,500 (from Groq).",
        provider="groq",
        model="llama-3.3-70b-versatile",
    )
    mock_meta_response = WhatsAppSendMessageResponse(
        messaging_product="whatsapp",
        messages=[WhatsAppMessageItem(id="wamid.OUTBOUND_GROQ_001")],
    )

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.ai.providers.groq.GroqProvider.generate", new_callable=AsyncMock) as mock_groq,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.side_effect = AIProviderTimeoutError("Gemini timed out")
        mock_groq.return_value = mock_groq_response
        mock_send.return_value = mock_meta_response

        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200

        # Both Gemini and Groq were invoked
        assert mock_gemini.await_count == 1
        assert mock_groq.await_count == 1

        # Outbound message was dispatched with Groq content
        assert mock_send.await_count == 1
        assert "from Groq" in mock_send.call_args[1]["message"]

    # Verify AI message persisted
    ai_msg = db_session.scalar(select(Message).where(Message.clinic_id == clinic_a.id, Message.sender_type == "ai"))
    assert ai_msg is not None
    assert "from Groq" in ai_msg.content
    assert ai_msg.external_message_id == "wamid.OUTBOUND_GROQ_001"


def test_gemini_429_triggers_groq_fallback_and_outbound(client, db_session, setup_data):
    clinic_a = setup_data["clinic_a"]
    app_secret = "meta_test_secret_123"

    payload = make_payload(
        phone_number_id="phone_id_clinic_a",
        from_phone="923001112233",
        msg_id="wamid.INCOMING_429",
        text="Hello",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.ai.providers.groq.GroqProvider.generate", new_callable=AsyncMock) as mock_groq,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.side_effect = AIRateLimitError("Gemini rate limited")
        mock_groq.return_value = AIResponse(content="Hello from Groq!", provider="groq", model="llama-3.3-70b-versatile")
        mock_send.return_value = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.OUT_429")])

        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200
        assert mock_groq.await_count == 1
        assert mock_send.await_count == 1


def test_gemini_5xx_triggers_groq_fallback_and_outbound(client, db_session, setup_data):
    app_secret = "meta_test_secret_123"

    payload = make_payload(
        phone_number_id="phone_id_clinic_a",
        from_phone="923001112233",
        msg_id="wamid.INCOMING_500",
        text="Hello 500",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.ai.providers.groq.GroqProvider.generate", new_callable=AsyncMock) as mock_groq,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.side_effect = AITemporaryServerError("Gemini 503 Overloaded")
        mock_groq.return_value = AIResponse(content="Hello from 503 fallback!", provider="groq", model="llama-3.3-70b-versatile")
        mock_send.return_value = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.OUT_500")])

        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200
        assert mock_groq.await_count == 1
        assert mock_send.await_count == 1


def test_gemini_auth_failure_does_not_call_groq_and_no_outbound(client, db_session, setup_data):
    clinic_a = setup_data["clinic_a"]
    app_secret = "meta_test_secret_123"

    payload = make_payload(
        phone_number_id="phone_id_clinic_a",
        from_phone="923001112233",
        msg_id="wamid.INCOMING_AUTH_ERR",
        text="Hello auth",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.ai.providers.groq.GroqProvider.generate", new_callable=AsyncMock) as mock_groq,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.side_effect = AIAuthenticationError("Invalid API key")

        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200

        # Groq must NOT be called for non-retryable config/auth error
        assert mock_groq.await_count == 0
        assert mock_send.await_count == 0

    # Customer message was saved, but no AI message
    messages = db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id)).all()
    assert len(messages) == 1
    assert messages[0].sender_type == "customer"


def test_both_ai_providers_fail_no_outbound_and_customer_message_remains_persisted(client, db_session, setup_data):
    clinic_a = setup_data["clinic_a"]
    app_secret = "meta_test_secret_123"

    payload = make_payload(
        phone_number_id="phone_id_clinic_a",
        from_phone="923001112233",
        msg_id="wamid.INCOMING_BOTH_FAIL",
        text="Both fail test",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.ai.providers.groq.GroqProvider.generate", new_callable=AsyncMock) as mock_groq,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.side_effect = AIProviderTimeoutError("Gemini timed out")
        mock_groq.side_effect = AIProviderTimeoutError("Groq timed out")

        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200
        assert mock_send.await_count == 0

    # Ensure customer message is persisted, but zero AI messages
    messages = db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id)).all()
    assert len(messages) == 1
    assert messages[0].sender_type == "customer"


def test_meta_authentication_failure_does_not_falsely_persist_ai_message(client, db_session, setup_data):
    clinic_a = setup_data["clinic_a"]
    app_secret = "meta_test_secret_123"

    payload = make_payload(
        phone_number_id="phone_id_clinic_a",
        from_phone="923001112233",
        msg_id="wamid.INCOMING_META_401",
        text="Meta auth failure test",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.return_value = AIResponse(content="AI answer", provider="gemini", model="gemini-1.5-flash")
        mock_send.side_effect = WhatsAppAuthenticationError("Invalid WhatsApp Access Token")

        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200

    # Ensure NO fake AI message was persisted
    ai_msgs = db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id, Message.sender_type == "ai")).all()
    assert len(ai_msgs) == 0


def test_meta_rate_limit_handled_cleanly(client, db_session, setup_data):
    app_secret = "meta_test_secret_123"

    payload = make_payload(
        phone_number_id="phone_id_clinic_a",
        from_phone="923001112233",
        msg_id="wamid.INCOMING_META_429",
        text="Meta 429 test",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.return_value = AIResponse(content="AI answer", provider="gemini", model="gemini-1.5-flash")
        mock_send.side_effect = WhatsAppRateLimitError("Meta rate limit reached")

        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200  # Handled cleanly without crashing


def test_tenant_isolation_in_ai_context(client, db_session, setup_data):
    clinic_a = setup_data["clinic_a"]
    clinic_b = setup_data["clinic_b"]
    app_secret = "meta_test_secret_123"

    # Message sent to Clinic A
    payload_a = make_payload(
        phone_number_id="phone_id_clinic_a",
        from_phone="923005559999",
        msg_id="wamid.TENANT_CHECK_A",
        text="What are your rates?",
    )
    raw_body_a = json.dumps(payload_a).encode("utf-8")
    sig_a = generate_webhook_signature(raw_body_a, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.return_value = AIResponse(content="Karachi Dental rates.", provider="gemini", model="gemini-1.5-flash")
        mock_send.return_value = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.OUT_A")])

        client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig_a}, content=raw_body_a)

        # Inspect prompt passed to Gemini: MUST contain Clinic A info & knowledge, NOT Clinic B
        call_messages = mock_gemini.call_args[0][0]
        system_content = next(m["content"] for m in call_messages if m["role"] == "system")

        assert "Karachi Dental Studio" in system_content
        assert "Scaling and Polishing Pricing" in system_content
        assert "PKR 4,500" in system_content

        # Clinic B knowledge MUST NOT be present
        assert "Hydrafacial" not in system_content
        assert "Lahore Aesthetic Clinic" not in system_content


def test_unsupported_message_type_does_not_invoke_ai_or_meta_outbound(client, db_session, setup_data):
    app_secret = "meta_test_secret_123"

    payload = make_payload(
        phone_number_id="phone_id_clinic_a",
        from_phone="923001112233",
        msg_id="wamid.IMAGE_MSG",
        text="",
        msg_type="image",
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
        assert mock_gemini.await_count == 0
        assert mock_send.await_count == 0


def test_status_webhook_does_not_invoke_ai_or_meta_outbound(client, db_session, setup_data):
    app_secret = "meta_test_secret_123"

    status_payload = {
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
                                "phone_number_id": "phone_id_clinic_a",
                            },
                            "statuses": [{"id": "wamid.OUTBOUND_123", "status": "read"}],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(status_payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200
        assert mock_gemini.await_count == 0
        assert mock_send.await_count == 0


def test_webhook_does_not_require_jwt_or_clinic_id_for_ai_pipeline(client, db_session, setup_data):
    app_secret = "meta_test_secret_123"

    payload = make_payload(
        phone_number_id="phone_id_clinic_a",
        from_phone="923001112233",
        msg_id="wamid.NO_JWT_AI",
        text="Hello without JWT",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.return_value = AIResponse(content="AI Reply without auth", provider="gemini", model="gemini-1.5-flash")
        mock_send.return_value = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.OUT_NO_JWT")])

        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200
        assert mock_send.await_count == 1


def test_outbound_meta_message_id_persisted_in_external_message_id(client, db_session, setup_data):
    clinic_a = setup_data["clinic_a"]
    app_secret = "meta_test_secret_123"

    payload = make_payload(
        phone_number_id="phone_id_clinic_a",
        from_phone="923001112233",
        msg_id="wamid.INCOMING_EXT_ID",
        text="Testing external message id",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.return_value = AIResponse(content="Reply", provider="gemini", model="gemini-1.5-flash")
        mock_send.return_value = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.PRECISE_OUTBOUND_ID_999")])

        client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)

    ai_msg = db_session.scalar(select(Message).where(Message.clinic_id == clinic_a.id, Message.sender_type == "ai"))
    assert ai_msg is not None
    assert ai_msg.external_message_id == "wamid.PRECISE_OUTBOUND_ID_999"


def test_no_secret_leakage_in_ai_pipeline(client, db_session, setup_data):
    app_secret = "meta_test_secret_123"
    secret_access_token = "clinic_a_secret_access_token"

    payload = make_payload(
        phone_number_id="phone_id_clinic_a",
        from_phone="923001112233",
        msg_id="wamid.SECRET_LEAK_CHECK",
        text="Test secret leak",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.return_value = AIResponse(content="Clean reply", provider="gemini", model="gemini-1.5-flash")
        mock_send.return_value = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.OUT_CLEAN")])

        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200
        assert secret_access_token not in res.text
        assert app_secret not in res.text


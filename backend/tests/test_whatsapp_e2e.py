import json
import logging
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
from app.integrations.whatsapp.exceptions import (
    WhatsAppAuthenticationError,
    WhatsAppNetworkError,
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
def e2e_setup(db_session):
    # Clinic A: Karachi Dental Studio
    clinic_a = Clinic(
        name="Karachi Dental Studio",
        slug="karachi-dental",
        timezone="Asia/Karachi",
        description="Premium dental clinic in Clifton Karachi",
        phone="+922135812345",
        email="info@karachidental.pk",
    )
    owner_a = User(email="owner@kds.pk", full_name="Dr. Tariq Khan", is_active=True)
    db_session.add_all([clinic_a, owner_a])
    db_session.commit()

    db_session.add(ClinicMembership(clinic_id=clinic_a.id, user_id=owner_a.id, role="owner"))
    whatsapp_a = WhatsAppAccount(
        clinic_id=clinic_a.id,
        phone_number="+923001234567",
        phone_number_id="meta_phone_id_clinic_a",
        business_account_id="waba_id_clinic_a",
        display_name="Karachi Dental Official",
        access_token="EAA_CLINIC_A_SECRET_TOKEN_999",
        is_active=True,
    )
    knowledge_a1 = KnowledgeDocument(
        clinic_id=clinic_a.id,
        title="Teeth Whitening Pricing & Details",
        content="Teeth Whitening at Karachi Dental Studio costs PKR 15,000 using Philips Zoom.",
        category="services",
        is_active=True,
    )
    knowledge_a2 = KnowledgeDocument(
        clinic_id=clinic_a.id,
        title="Clinic Hours",
        content="Our clinic is open Monday to Saturday from 11:00 AM to 8:00 PM.",
        category="general",
        is_active=True,
    )

    # Clinic B: Lahore Aesthetic Clinic
    clinic_b = Clinic(
        name="Lahore Aesthetic Clinic",
        slug="lahore-aesthetic",
        timezone="Asia/Karachi",
        description="Aesthetics and dermatology in Gulberg Lahore",
    )
    db_session.add(clinic_b)
    db_session.commit()

    whatsapp_b = WhatsAppAccount(
        clinic_id=clinic_b.id,
        phone_number="+923219876543",
        phone_number_id="meta_phone_id_clinic_b",
        display_name="Lahore Aesthetic Official",
        access_token="EAA_CLINIC_B_SECRET_TOKEN_888",
        is_active=True,
    )
    knowledge_b = KnowledgeDocument(
        clinic_id=clinic_b.id,
        title="Botox Pricing",
        content="Botox treatment cost is PKR 35,000 per area.",
        category="services",
        is_active=True,
    )

    db_session.add_all([whatsapp_a, knowledge_a1, knowledge_a2, whatsapp_b, knowledge_b])
    db_session.commit()

    return {
        "clinic_a": clinic_a,
        "whatsapp_a": whatsapp_a,
        "knowledge_a1": knowledge_a1,
        "knowledge_a2": knowledge_a2,
        "clinic_b": clinic_b,
        "whatsapp_b": whatsapp_b,
        "knowledge_b": knowledge_b,
    }


def make_webhook_payload(
    phone_number_id: str,
    from_phone: str,
    msg_id: str,
    text: str,
    contact_name: str = "Ayesha Malik",
    timestamp: str = "1725177600",
    msg_type: str = "text",
) -> dict:
    msg_obj = {
        "from": from_phone,
        "id": msg_id,
        "timestamp": timestamp,
        "type": msg_type,
    }
    if msg_type == "text":
        msg_obj["text"] = {"body": text}

    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_E2E_999",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+923001234567",
                                "phone_number_id": phone_number_id,
                            },
                            "contacts": [
                                {
                                    "profile": {"name": contact_name},
                                    "wa_id": from_phone.lstrip("+"),
                                }
                            ],
                            "messages": [msg_obj],
                        },
                    }
                ],
            }
        ],
    }


# ============================================================================
# CHUNK 6E End-to-End Tests
# ============================================================================


def test_e2e_complete_flow_success(client, db_session, e2e_setup):
    clinic_a = e2e_setup["clinic_a"]
    app_secret = "meta_app_secret_e2e"

    payload = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923005557788",
        msg_id="wamid.E2E_SUCCESS_001",
        text="How much does teeth whitening cost and what are your hours?",
        contact_name="Ayesha Malik",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    ai_reply_text = "Teeth Whitening at Karachi Dental Studio costs PKR 15,000. We are open Monday to Saturday from 11:00 AM to 8:00 PM."
    mock_gemini_resp = AIResponse(content=ai_reply_text, provider="gemini", model="gemini-1.5-flash")
    mock_meta_resp = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.OUTBOUND_META_001")])

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.ai.providers.groq.GroqProvider.generate", new_callable=AsyncMock) as mock_groq,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.return_value = mock_gemini_resp
        mock_send.return_value = mock_meta_resp

        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

        # Assert Gemini primary invoked, Groq untouched
        assert mock_gemini.await_count == 1
        assert mock_groq.await_count == 0

        # Assert Meta Outbound invoked
        assert mock_send.await_count == 1
        assert mock_send.call_args[1]["recipient_phone"] == "+923005557788"
        assert mock_send.call_args[1]["message"] == ai_reply_text

    # Assert CRM Entities Created
    lead = db_session.scalar(select(Lead).where(Lead.clinic_id == clinic_a.id, Lead.phone == "+923005557788"))
    assert lead is not None
    assert lead.full_name == "Ayesha Malik"
    assert lead.source == "whatsapp"

    conv = db_session.scalar(select(Conversation).where(Conversation.clinic_id == clinic_a.id, Conversation.lead_id == lead.id))
    assert conv is not None
    assert conv.channel == "whatsapp"
    assert conv.status == "open"

    messages = db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id).order_by(Message.created_at)).all()
    assert len(messages) == 2
    assert messages[0].sender_type == "customer"
    assert messages[0].external_message_id == "wamid.E2E_SUCCESS_001"
    assert messages[1].sender_type == "ai"
    assert messages[1].external_message_id == "wamid.OUTBOUND_META_001"
    assert messages[1].content == ai_reply_text


def test_e2e_existing_lead_and_conversation_reuse(client, db_session, e2e_setup):
    clinic_a = e2e_setup["clinic_a"]
    app_secret = "meta_app_secret_e2e"

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.side_effect = [
            AIResponse(content="First AI Reply", provider="gemini", model="gemini-1.5-flash"),
            AIResponse(content="Second AI Reply", provider="gemini", model="gemini-1.5-flash"),
        ]
        mock_send.side_effect = [
            WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.OUT_1")]),
            WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.OUT_2")]),
        ]

        # Message 1
        p1 = make_webhook_payload("meta_phone_id_clinic_a", "923005557788", "wamid.MSG_1", "Hello")
        b1 = json.dumps(p1).encode("utf-8")
        client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": generate_webhook_signature(b1, app_secret)}, content=b1)

        # Message 2 from same customer
        p2 = make_webhook_payload("meta_phone_id_clinic_a", "923005557788", "wamid.MSG_2", "I want an appointment tomorrow")
        b2 = json.dumps(p2).encode("utf-8")
        client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": generate_webhook_signature(b2, app_secret)}, content=b2)

    # Exactly 1 lead and 1 conversation
    leads = db_session.scalars(select(Lead).where(Lead.clinic_id == clinic_a.id)).all()
    convs = db_session.scalars(select(Conversation).where(Conversation.clinic_id == clinic_a.id)).all()
    assert len(leads) == 1
    assert len(convs) == 1

    # 4 messages: 2 customer + 2 AI
    messages = db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id)).all()
    assert len(messages) == 4
    customer_msgs = [m for m in messages if m.sender_type == "customer"]
    ai_msgs = [m for m in messages if m.sender_type == "ai"]
    assert len(customer_msgs) == 2
    assert len(ai_msgs) == 2


def test_e2e_full_idempotency_duplicate_message_id(client, db_session, e2e_setup):
    clinic_a = e2e_setup["clinic_a"]
    app_secret = "meta_app_secret_e2e"

    payload = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923005557788",
        msg_id="wamid.IDEMPOTENT_TEST",
        text="Idempotency check",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.return_value = AIResponse(content="AI Response", provider="gemini", model="gemini-1.5-flash")
        mock_send.return_value = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.OUT_IDEMP")])

        # Delivery 1
        res1 = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res1.status_code == 200

        # Delivery 2 (Duplicate Meta retry)
        res2 = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res2.status_code == 200

        # Delivery 3
        res3 = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res3.status_code == 200

        # AI and Meta Outbound must ONLY have been called ONCE
        assert mock_gemini.await_count == 1
        assert mock_send.await_count == 1

    messages = db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id)).all()
    assert len(messages) == 2  # 1 customer + 1 AI


def test_e2e_gemini_transient_failure_groq_fallback(client, db_session, e2e_setup):
    clinic_a = e2e_setup["clinic_a"]
    app_secret = "meta_app_secret_e2e"

    payload = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923005557788",
        msg_id="wamid.FALLBACK_MSG",
        text="What are your fees?",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    groq_reply = "Teeth whitening is PKR 15,000 (answered via Groq fallback)."

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.ai.providers.groq.GroqProvider.generate", new_callable=AsyncMock) as mock_groq,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.side_effect = AITemporaryServerError("Gemini 503 Service Unavailable")
        mock_groq.return_value = AIResponse(content=groq_reply, provider="groq", model="llama-3.3-70b-versatile")
        mock_send.return_value = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.OUT_GROQ")])

        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200

        # Assert Gemini failed and Groq succeeded
        assert mock_gemini.await_count == 1
        assert mock_groq.await_count == 1
        assert mock_send.call_args[1]["message"] == groq_reply

    ai_msg = db_session.scalar(select(Message).where(Message.clinic_id == clinic_a.id, Message.sender_type == "ai"))
    assert ai_msg is not None
    assert ai_msg.content == groq_reply


def test_e2e_gemini_auth_failure_no_groq_fallback(client, db_session, e2e_setup):
    clinic_a = e2e_setup["clinic_a"]
    app_secret = "meta_app_secret_e2e"

    payload = make_payload = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923005557788",
        msg_id="wamid.AUTH_FAIL_MSG",
        text="Auth check",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.ai.providers.groq.GroqProvider.generate", new_callable=AsyncMock) as mock_groq,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.side_effect = AIAuthenticationError("Invalid Gemini API Key")

        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200

        # Groq must NOT be invoked for non-retryable auth errors
        assert mock_groq.await_count == 0
        assert mock_send.await_count == 0

    # Inbound message remains persisted in database
    msgs = db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id)).all()
    assert len(msgs) == 1
    assert msgs[0].sender_type == "customer"


def test_e2e_both_ai_providers_fail(client, db_session, e2e_setup):
    clinic_a = e2e_setup["clinic_a"]
    app_secret = "meta_app_secret_e2e"

    payload = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923005557788",
        msg_id="wamid.BOTH_FAIL",
        text="Both providers fail test",
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

    # Inbound message preserved, zero AI messages
    msgs = db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id)).all()
    assert len(msgs) == 1
    assert msgs[0].sender_type == "customer"


def test_e2e_meta_outbound_failure_classification(client, db_session, e2e_setup):
    clinic_a = e2e_setup["clinic_a"]
    app_secret = "meta_app_secret_e2e"

    payload = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923005557788",
        msg_id="wamid.META_FAIL_MSG",
        text="Meta send failure",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.return_value = AIResponse(content="AI message", provider="gemini", model="gemini-1.5-flash")
        mock_send.side_effect = WhatsAppRateLimitError("Meta Rate Limit Exceeded")

        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200

    # Verify no fake AI message was persisted
    ai_msgs = db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id, Message.sender_type == "ai")).all()
    assert len(ai_msgs) == 0


def test_e2e_tenant_isolation_full_pipeline(client, db_session, e2e_setup):
    clinic_a = e2e_setup["clinic_a"]
    clinic_b = e2e_setup["clinic_b"]
    app_secret = "meta_app_secret_e2e"

    payload_a = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923001110000",
        msg_id="wamid.TENANT_ISO_A",
        text="Rates inquiry",
    )
    raw_body_a = json.dumps(payload_a).encode("utf-8")
    sig_a = generate_webhook_signature(raw_body_a, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.return_value = AIResponse(content="Dental reply", provider="gemini", model="gemini-1.5-flash")
        mock_send.return_value = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.OUT_A")])

        client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig_a}, content=raw_body_a)

    # Clinic A has lead, conversation, and messages
    assert len(db_session.scalars(select(Lead).where(Lead.clinic_id == clinic_a.id)).all()) == 1
    assert len(db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id)).all()) == 2

    # Clinic B has ZERO records created
    assert len(db_session.scalars(select(Lead).where(Lead.clinic_id == clinic_b.id)).all()) == 0
    assert len(db_session.scalars(select(Conversation).where(Conversation.clinic_id == clinic_b.id)).all()) == 0
    assert len(db_session.scalars(select(Message).where(Message.clinic_id == clinic_b.id)).all()) == 0


def test_e2e_credential_isolation(client, db_session, e2e_setup):
    app_secret = "meta_app_secret_e2e"

    payload_a = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923001110000",
        msg_id="wamid.CRED_CHECK",
        text="Check credentials",
    )
    raw_body_a = json.dumps(payload_a).encode("utf-8")
    sig_a = generate_webhook_signature(raw_body_a, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.return_value = AIResponse(content="Reply", provider="gemini", model="gemini-1.5-flash")
        mock_send.return_value = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.OUT_CRED")])

        client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig_a}, content=raw_body_a)

        # Verify WhatsApp client was initialized with Clinic A's access token
        assert mock_send.await_count == 1


def test_e2e_ai_context_isolation(client, db_session, e2e_setup):
    app_secret = "meta_app_secret_e2e"

    payload_a = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923001110000",
        msg_id="wamid.AI_CONTEXT_CHECK",
        text="What treatments do you offer?",
    )
    raw_body_a = json.dumps(payload_a).encode("utf-8")
    sig_a = generate_webhook_signature(raw_body_a, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.return_value = AIResponse(content="We offer teeth whitening.", provider="gemini", model="gemini-1.5-flash")
        mock_send.return_value = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.OUT_CTX")])

        client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig_a}, content=raw_body_a)

        # Inspect system prompt passed to Gemini
        call_messages = mock_gemini.call_args[0][0]
        system_msg = next(m["content"] for m in call_messages if m["role"] == "system")

        # Clinic A content present
        assert "Karachi Dental Studio" in system_msg
        assert "Teeth Whitening" in system_msg
        assert "PKR 15,000" in system_msg

        # Clinic B content MUST be absent
        assert "Lahore Aesthetic Clinic" not in system_msg
        assert "Botox" not in system_msg
        assert "PKR 35,000" not in system_msg


def test_e2e_multi_turn_conversation_history(client, db_session, e2e_setup):
    clinic_a = e2e_setup["clinic_a"]
    app_secret = "meta_app_secret_e2e"

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.side_effect = [
            AIResponse(content="Sure, what day works for you?", provider="gemini", model="gemini-1.5-flash"),
            AIResponse(content="Great, tomorrow at 3 PM is available.", provider="gemini", model="gemini-1.5-flash"),
        ]
        mock_send.return_value = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.OUT_TURN")])

        # Turn 1
        p1 = make_webhook_payload("meta_phone_id_clinic_a", "923009998888", "wamid.T1", "Hi, I need an appointment.")
        b1 = json.dumps(p1).encode("utf-8")
        client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": generate_webhook_signature(b1, app_secret)}, content=b1)

        # Turn 2
        p2 = make_webhook_payload("meta_phone_id_clinic_a", "923009998888", "wamid.T2", "Tomorrow.")
        b2 = json.dumps(p2).encode("utf-8")
        client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": generate_webhook_signature(b2, app_secret)}, content=b2)

        # Inspect Turn 2 call messages to Gemini: must contain history from Turn 1!
        turn2_messages = mock_gemini.call_args[0][0]
        user_messages = [m for m in turn2_messages if m["role"] == "user"]
        assistant_messages = [m for m in turn2_messages if m["role"] == "assistant"]

        assert any("Hi, I need an appointment." in m["content"] for m in user_messages)
        assert any("Sure, what day works for you?" in m["content"] for m in assistant_messages)
        assert turn2_messages[-1]["content"] == "Tomorrow."


def test_e2e_unsupported_message_types_safely_ignored(client, db_session, e2e_setup):
    clinic_a = e2e_setup["clinic_a"]
    app_secret = "meta_app_secret_e2e"

    payload = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923005557788",
        msg_id="wamid.IMAGE_UNSUPPORTED",
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

    assert len(db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id)).all()) == 0


def test_e2e_status_webhooks_safely_ignored(client, db_session, e2e_setup):
    clinic_a = e2e_setup["clinic_a"]
    app_secret = "meta_app_secret_e2e"

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
                                "phone_number_id": "meta_phone_id_clinic_a",
                            },
                            "statuses": [{"id": "wamid.OUT_123", "status": "read"}],
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


def test_e2e_invalid_signature_full_boundary(client, db_session, e2e_setup):
    payload = make_webhook_payload("meta_phone_id_clinic_a", "923005557788", "wamid.HACK", "Hacking attempt")
    raw_body = json.dumps(payload).encode("utf-8")

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", "valid_secret"),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": "sha256=" + "0" * 64},
            content=raw_body,
        )
        assert res.status_code == 403
        assert mock_gemini.await_count == 0
        assert mock_send.await_count == 0

    assert len(db_session.scalars(select(Lead)).all()) == 0
    assert len(db_session.scalars(select(Conversation)).all()) == 0
    assert len(db_session.scalars(select(Message)).all()) == 0


def test_e2e_malformed_signed_payload(client, db_session):
    app_secret = "meta_app_secret_e2e"
    malformed_raw = b"THIS IS NOT JSON {{{{"
    sig = generate_webhook_signature(malformed_raw, app_secret)

    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": sig},
            content=malformed_raw,
        )
        assert res.status_code == 400


def test_e2e_unknown_whatsapp_account(client, db_session):
    app_secret = "meta_app_secret_e2e"
    payload = make_webhook_payload("unregistered_phone_id_999", "923005557788", "wamid.UNKNOWN", "Hello")
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

    assert len(db_session.scalars(select(Lead)).all()) == 0


def test_e2e_logging_security_no_secret_leakage(client, caplog, e2e_setup):
    app_secret = "secret_meta_app_key_999"
    secret_token = "EAA_CLINIC_A_SECRET_TOKEN_999"

    payload = make_webhook_payload("meta_phone_id_clinic_a", "923005557788", "wamid.LOG_CHECK", "Secret logging check")
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        caplog.at_level(logging.DEBUG),
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.return_value = AIResponse(content="Safe response", provider="gemini", model="gemini-1.5-flash")
        mock_send.return_value = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.OUT_LOG")])

        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200

    log_text = caplog.text
    assert app_secret not in log_text
    assert secret_token not in log_text
    assert "EAA_" not in log_text


def test_e2e_webhook_replay_triple_submission(client, db_session, e2e_setup):
    clinic_a = e2e_setup["clinic_a"]
    app_secret = "meta_app_secret_e2e"

    payload = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923005557788",
        msg_id="wamid.REPLAY_EXACT_ID",
        text="Replay test",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        mock_gemini.return_value = AIResponse(content="Replay AI answer", provider="gemini", model="gemini-1.5-flash")
        mock_send.return_value = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.OUT_REPLAY")])

        # 3 consecutive submissions of the exact same signed payload
        res1 = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        res2 = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        res3 = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)

        assert res1.status_code == 200
        assert res2.status_code == 200
        assert res3.status_code == 200

        # AI and Meta Outbound must ONLY be called ONCE
        assert mock_gemini.await_count == 1
        assert mock_send.await_count == 1

    messages = db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id)).all()
    assert len(messages) == 2  # 1 customer + 1 AI


def test_e2e_empty_or_invalid_customer_data(client, db_session, e2e_setup):
    clinic_a = e2e_setup["clinic_a"]
    app_secret = "meta_app_secret_e2e"

    # Missing text body
    payload_empty_text = {
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
                                "phone_number_id": "meta_phone_id_clinic_a",
                            },
                            "messages": [{"from": "923001234567", "id": "wamid.EMPTY", "type": "text", "text": {"body": ""}}],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload_empty_text).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
    ):
        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200
        assert mock_gemini.await_count == 0

    assert len(db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id)).all()) == 0


def test_e2e_final_acceptance_production_lifecycle(client, db_session, e2e_setup):
    clinic_a = e2e_setup["clinic_a"]
    app_secret = "meta_app_secret_e2e"

    with (
        patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret),
        patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini,
        patch("app.ai.providers.groq.GroqProvider.generate", new_callable=AsyncMock) as mock_groq,
        patch("app.integrations.whatsapp.client.WhatsAppClient.send_text_message", new_callable=AsyncMock) as mock_send,
    ):
        # Step 1: Inbound message -> Gemini primary succeeds -> Outbound Meta send
        mock_gemini.return_value = AIResponse(content="Gemini: Whitening is PKR 15k.", provider="gemini", model="gemini-1.5-flash")
        mock_send.return_value = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.FINAL_OUT_1")])

        p1 = make_webhook_payload("meta_phone_id_clinic_a", "923005557788", "wamid.FINAL_IN_1", "Hi, whitening price?")
        b1 = json.dumps(p1).encode("utf-8")
        res1 = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": generate_webhook_signature(b1, app_secret)}, content=b1)
        assert res1.status_code == 200

        # Step 2: Inbound message 2 -> Gemini fails -> Groq fallback succeeds -> Outbound Meta send
        mock_gemini.side_effect = AIProviderTimeoutError("Gemini timed out")
        mock_groq.return_value = AIResponse(content="Groq: We are open until 8 PM.", provider="groq", model="llama-3.3-70b-versatile")
        mock_send.return_value = WhatsAppSendMessageResponse(messages=[WhatsAppMessageItem(id="wamid.FINAL_OUT_2")])

        p2 = make_webhook_payload("meta_phone_id_clinic_a", "923005557788", "wamid.FINAL_IN_2", "What are your hours?")
        b2 = json.dumps(p2).encode("utf-8")
        res2 = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": generate_webhook_signature(b2, app_secret)}, content=b2)
        assert res2.status_code == 200

        # Step 3: Replay message 2 -> Idempotent skip
        res3 = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": generate_webhook_signature(b2, app_secret)}, content=b2)
        assert res3.status_code == 200

    # Final DB assertions: 1 lead, 1 conversation, 4 messages
    leads = db_session.scalars(select(Lead).where(Lead.clinic_id == clinic_a.id)).all()
    convs = db_session.scalars(select(Conversation).where(Conversation.clinic_id == clinic_a.id)).all()
    messages = db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id)).all()

    assert len(leads) == 1
    assert len(convs) == 1
    assert len(messages) == 4
    customer_msgs = [m for m in messages if m.sender_type == "customer"]
    ai_msgs = [m for m in messages if m.sender_type == "ai"]
    assert len(customer_msgs) == 2
    assert len(ai_msgs) == 2
    assert any("Gemini" in m.content for m in ai_msgs)
    assert any("Groq" in m.content for m in ai_msgs)


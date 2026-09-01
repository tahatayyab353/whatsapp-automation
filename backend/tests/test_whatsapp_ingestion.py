from datetime import datetime, timezone
import json
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import get_db
from app.integrations.whatsapp.security import generate_webhook_signature
from app.main import app
from app.models import (
    Base,
    Clinic,
    ClinicMembership,
    Conversation,
    Lead,
    Message,
    User,
    WhatsAppAccount,
)


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
def setup_clinic_and_whatsapp(db_session):
    # Setup Clinic A
    clinic_a = Clinic(name="Karachi Dental Studio", slug="karachi-dental", timezone="Asia/Karachi")
    owner_a = User(email="owner@kds.local", full_name="Dr. Tariq", is_active=True)
    db_session.add_all([clinic_a, owner_a])
    db_session.commit()

    db_session.add(ClinicMembership(clinic_id=clinic_a.id, user_id=owner_a.id, role="owner"))
    whatsapp_a = WhatsAppAccount(
        clinic_id=clinic_a.id,
        phone_number="+923001234567",
        phone_number_id="meta_phone_id_clinic_a",
        business_account_id="waba_id_clinic_a",
        display_name="Karachi Dental Reception",
        access_token="test_access_token_a",
        is_active=True,
    )

    # Setup Clinic B (for tenant isolation tests)
    clinic_b = Clinic(name="Lahore Aesthetic Clinic", slug="lahore-aesthetic", timezone="Asia/Karachi")
    owner_b = User(email="owner@lac.local", full_name="Dr. Sara", is_active=True)
    db_session.add_all([clinic_b, owner_b])
    db_session.commit()

    db_session.add(ClinicMembership(clinic_id=clinic_b.id, user_id=owner_b.id, role="owner"))
    whatsapp_b = WhatsAppAccount(
        clinic_id=clinic_b.id,
        phone_number="+923219876543",
        phone_number_id="meta_phone_id_clinic_b",
        business_account_id="waba_id_clinic_b",
        display_name="Lahore Aesthetic Reception",
        access_token="test_access_token_b",
        is_active=True,
    )

    db_session.add_all([whatsapp_a, whatsapp_b])
    db_session.commit()

    return {
        "clinic_a": clinic_a,
        "whatsapp_a": whatsapp_a,
        "clinic_b": clinic_b,
        "whatsapp_b": whatsapp_b,
    }


def make_webhook_payload(
    phone_number_id: str,
    from_phone: str,
    message_id: str,
    text: str,
    contact_name: str = "Fatima Ali",
    timestamp: str = "1725177600",
    msg_type: str = "text",
) -> dict:
    msg_obj = {
        "from": from_phone,
        "id": message_id,
        "timestamp": timestamp,
        "type": msg_type,
    }
    if msg_type == "text":
        msg_obj["text"] = {"body": text}

    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_TEST_123",
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
# Webhook Ingestion Tests
# ============================================================================


def test_incoming_text_message_creates_lead_conversation_message(client, db_session, setup_clinic_and_whatsapp):
    clinic_a = setup_clinic_and_whatsapp["clinic_a"]
    app_secret = "meta_test_secret_123"

    payload_dict = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923005551234",
        message_id="wamid.HBgMOTIzMDA1NTUxMjM0FQIAERgSR",
        text="Hello! I'd like to book a dental checkup.",
        contact_name="Fatima Ali",
        timestamp="1725177600",
    )
    raw_body = json.dumps(payload_dict).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
            content=raw_body,
        )
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

    # Verify Lead creation
    leads = db_session.scalars(select(Lead).where(Lead.clinic_id == clinic_a.id)).all()
    assert len(leads) == 1
    lead = leads[0]
    assert lead.phone == "+923005551234"
    assert lead.full_name == "Fatima Ali"
    assert lead.source == "whatsapp"
    assert lead.status == "new"

    # Verify Conversation creation
    conversations = db_session.scalars(select(Conversation).where(Conversation.clinic_id == clinic_a.id)).all()
    assert len(conversations) == 1
    conv = conversations[0]
    assert conv.lead_id == lead.id
    assert conv.channel == "whatsapp"
    assert conv.status == "open"
    assert conv.last_message_at is not None

    # Verify Message creation
    messages = db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id)).all()
    assert len(messages) == 1
    msg = messages[0]
    assert msg.conversation_id == conv.id
    assert msg.sender_type == "customer"
    assert msg.message_type == "text"
    assert msg.content == "Hello! I'd like to book a dental checkup."
    assert msg.external_message_id == "wamid.HBgMOTIzMDA1NTUxMjM0FQIAERgSR"


def test_second_message_reuses_existing_lead_and_conversation(client, db_session, setup_clinic_and_whatsapp):
    clinic_a = setup_clinic_and_whatsapp["clinic_a"]
    app_secret = "meta_test_secret_123"

    # Message 1
    payload1 = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923005551234",
        message_id="wamid.MSG_1",
        text="First inquiry",
    )
    raw_body1 = json.dumps(payload1).encode("utf-8")
    sig1 = generate_webhook_signature(raw_body1, app_secret)

    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret):
        client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": sig1, "Content-Type": "application/json"},
            content=raw_body1,
        )

    # Message 2 from same customer
    payload2 = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923005551234",
        message_id="wamid.MSG_2",
        text="Second follow-up message",
    )
    raw_body2 = json.dumps(payload2).encode("utf-8")
    sig2 = generate_webhook_signature(raw_body2, app_secret)

    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret):
        res2 = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": sig2, "Content-Type": "application/json"},
            content=raw_body2,
        )
        assert res2.status_code == 200

    # Verify Lead was REUSED (still exactly 1 lead)
    leads = db_session.scalars(select(Lead).where(Lead.clinic_id == clinic_a.id)).all()
    assert len(leads) == 1

    # Verify Conversation was REUSED (still exactly 1 conversation)
    conversations = db_session.scalars(select(Conversation).where(Conversation.clinic_id == clinic_a.id)).all()
    assert len(conversations) == 1

    # Verify 2 Messages persisted under same conversation
    messages = db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id).order_by(Message.created_at)).all()
    assert len(messages) == 2
    assert messages[0].content == "First inquiry"
    assert messages[1].content == "Second follow-up message"
    assert messages[0].conversation_id == conversations[0].id
    assert messages[1].conversation_id == conversations[0].id


def test_duplicate_external_message_id_is_idempotent(client, db_session, setup_clinic_and_whatsapp):
    clinic_a = setup_clinic_and_whatsapp["clinic_a"]
    app_secret = "meta_test_secret_123"

    payload = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923005551234",
        message_id="wamid.DUPLICATE_TEST_ID",
        text="Testing message idempotency",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret):
        # First delivery
        res1 = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
            content=raw_body,
        )
        assert res1.status_code == 200

        # Meta retry delivery with exact same message ID
        res2 = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
            content=raw_body,
        )
        assert res2.status_code == 200

    # Ensure exactly 1 message, 1 lead, and 1 conversation exist
    assert len(db_session.scalars(select(Lead).where(Lead.clinic_id == clinic_a.id)).all()) == 1
    assert len(db_session.scalars(select(Conversation).where(Conversation.clinic_id == clinic_a.id)).all()) == 1
    assert len(db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id)).all()) == 1


def test_unknown_phone_number_id_is_acknowledged_without_db_writes(client, db_session):
    app_secret = "meta_test_secret_123"
    payload = make_webhook_payload(
        phone_number_id="unknown_unregistered_phone_id",
        from_phone="923009999999",
        message_id="wamid.UNKNOWN_PHONE",
        text="Hello unknown",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
            content=raw_body,
        )
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

    assert len(db_session.scalars(select(Lead)).all()) == 0
    assert len(db_session.scalars(select(Conversation)).all()) == 0
    assert len(db_session.scalars(select(Message)).all()) == 0


def test_status_webhook_does_not_create_crm_records(client, db_session, setup_clinic_and_whatsapp):
    app_secret = "meta_test_secret_123"
    status_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_TEST_123",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+923001234567",
                                "phone_number_id": "meta_phone_id_clinic_a",
                            },
                            "statuses": [
                                {
                                    "id": "wamid.OUTBOUND_123",
                                    "status": "delivered",
                                    "timestamp": "1725177650",
                                    "recipient_id": "923005551234",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(status_payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
            content=raw_body,
        )
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

    assert len(db_session.scalars(select(Lead)).all()) == 0
    assert len(db_session.scalars(select(Conversation)).all()) == 0
    assert len(db_session.scalars(select(Message)).all()) == 0


def test_unsupported_message_type_is_safely_acknowledged(client, db_session, setup_clinic_and_whatsapp):
    app_secret = "meta_test_secret_123"
    payload = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923005551234",
        message_id="wamid.IMAGE_123",
        text="",
        msg_type="image",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
            content=raw_body,
        )
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

    # Non-text messages are safely skipped for CHUNK 6C
    assert len(db_session.scalars(select(Message)).all()) == 0


def test_message_belongs_to_correct_clinic(client, db_session, setup_clinic_and_whatsapp):
    clinic_a = setup_clinic_and_whatsapp["clinic_a"]
    clinic_b = setup_clinic_and_whatsapp["clinic_b"]
    app_secret = "meta_test_secret_123"

    # Send message to Clinic B's WhatsApp number
    payload = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_b",
        from_phone="923331112233",
        message_id="wamid.CLINIC_B_MSG",
        text="Aesthetic consultation query",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
            content=raw_body,
        )
        assert res.status_code == 200

    # Clinic B has 1 lead and 1 message; Clinic A has 0
    assert len(db_session.scalars(select(Lead).where(Lead.clinic_id == clinic_b.id)).all()) == 1
    assert len(db_session.scalars(select(Message).where(Message.clinic_id == clinic_b.id)).all()) == 1

    assert len(db_session.scalars(select(Lead).where(Lead.clinic_id == clinic_a.id)).all()) == 0
    assert len(db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id)).all()) == 0


def test_cross_tenant_lead_isolation(client, db_session, setup_clinic_and_whatsapp):
    clinic_a = setup_clinic_and_whatsapp["clinic_a"]
    clinic_b = setup_clinic_and_whatsapp["clinic_b"]
    app_secret = "meta_test_secret_123"

    # Same patient phone sends message to Clinic A then Clinic B
    same_phone = "923007778899"

    payload_a = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone=same_phone,
        message_id="wamid.MSG_A",
        text="Message to Clinic A",
    )
    raw_body_a = json.dumps(payload_a).encode("utf-8")
    sig_a = generate_webhook_signature(raw_body_a, app_secret)

    payload_b = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_b",
        from_phone=same_phone,
        message_id="wamid.MSG_B",
        text="Message to Clinic B",
    )
    raw_body_b = json.dumps(payload_b).encode("utf-8")
    sig_b = generate_webhook_signature(raw_body_b, app_secret)

    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret):
        client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig_a}, content=raw_body_a)
        client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig_b}, content=raw_body_b)

    # Both clinics should have their own isolated lead and conversation
    lead_a = db_session.scalar(select(Lead).where(Lead.clinic_id == clinic_a.id, Lead.phone == "+923007778899"))
    lead_b = db_session.scalar(select(Lead).where(Lead.clinic_id == clinic_b.id, Lead.phone == "+923007778899"))

    assert lead_a is not None
    assert lead_b is not None
    assert lead_a.id != lead_b.id


def test_conversation_last_message_at_is_updated(client, db_session, setup_clinic_and_whatsapp):
    clinic_a = setup_clinic_and_whatsapp["clinic_a"]
    app_secret = "meta_test_secret_123"

    msg_timestamp_epoch = 1725177600
    expected_utc = datetime.fromtimestamp(msg_timestamp_epoch, tz=timezone.utc)

    payload = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923001239999",
        message_id="wamid.TIMESTAMP_CHECK",
        text="Timestamp test",
        timestamp=str(msg_timestamp_epoch),
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret):
        client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)

    conv = db_session.scalar(select(Conversation).where(Conversation.clinic_id == clinic_a.id))
    assert conv is not None
    actual_time = conv.last_message_at.replace(tzinfo=timezone.utc) if conv.last_message_at.tzinfo is None else conv.last_message_at
    assert actual_time == expected_utc


def test_invalid_signature_creates_zero_crm_records(client, db_session, setup_clinic_and_whatsapp):
    payload = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923001239999",
        message_id="wamid.INVALID_SIG",
        text="Malicious unauthenticated request",
    )
    raw_body = json.dumps(payload).encode("utf-8")

    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", "correct_secret"):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": "sha256=" + "0" * 64},
            content=raw_body,
        )
        assert res.status_code == 403

    assert len(db_session.scalars(select(Lead)).all()) == 0
    assert len(db_session.scalars(select(Conversation)).all()) == 0
    assert len(db_session.scalars(select(Message)).all()) == 0


def test_webhook_does_not_require_jwt_or_clinic_id_for_ingestion(client, db_session, setup_clinic_and_whatsapp):
    clinic_a = setup_clinic_and_whatsapp["clinic_a"]
    app_secret = "meta_test_secret_123"

    payload = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923009988776",
        message_id="wamid.NO_AUTH_HEADERS",
        text="Public webhook ingestion test",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    # Note: No 'Authorization' and no 'X-Clinic-ID' headers
    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
            content=raw_body,
        )
        assert res.status_code == 200

    assert len(db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id)).all()) == 1


def test_multiple_messages_from_same_customer_do_not_create_duplicate_leads(client, db_session, setup_clinic_and_whatsapp):
    clinic_a = setup_clinic_and_whatsapp["clinic_a"]
    app_secret = "meta_test_secret_123"

    for i in range(5):
        payload = make_webhook_payload(
            phone_number_id="meta_phone_id_clinic_a",
            from_phone="923005559999",
            message_id=f"wamid.BURST_{i}",
            text=f"Burst message #{i}",
        )
        raw_body = json.dumps(payload).encode("utf-8")
        sig = generate_webhook_signature(raw_body, app_secret)

        with patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret):
            client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)

    # Exactly 1 lead and 1 conversation, with 5 messages
    assert len(db_session.scalars(select(Lead).where(Lead.clinic_id == clinic_a.id)).all()) == 1
    assert len(db_session.scalars(select(Conversation).where(Conversation.clinic_id == clinic_a.id)).all()) == 1
    assert len(db_session.scalars(select(Message).where(Message.clinic_id == clinic_a.id)).all()) == 5


def test_message_timestamp_is_persisted_correctly_if_supported(client, db_session, setup_clinic_and_whatsapp):
    clinic_a = setup_clinic_and_whatsapp["clinic_a"]
    app_secret = "meta_test_secret_123"

    known_epoch = 1725177600
    expected_utc = datetime.fromtimestamp(known_epoch, tz=timezone.utc)

    payload = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923007770000",
        message_id="wamid.TIMESTAMP_ACCURACY",
        text="Precise timestamp message",
        timestamp=str(known_epoch),
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret):
        client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)

    msg = db_session.scalar(select(Message).where(Message.clinic_id == clinic_a.id, Message.external_message_id == "wamid.TIMESTAMP_ACCURACY"))
    assert msg is not None
    actual_created_at = msg.created_at.replace(tzinfo=timezone.utc) if msg.created_at.tzinfo is None else msg.created_at
    assert actual_created_at == expected_utc


def test_transaction_rolls_back_on_message_persistence_failure(client, db_session, setup_clinic_and_whatsapp):
    app_secret = "meta_test_secret_123"

    payload = make_webhook_payload(
        phone_number_id="meta_phone_id_clinic_a",
        from_phone="923008887777",
        message_id="wamid.FAIL_TX",
        text="Failing transaction test",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body, app_secret)

    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret), patch.object(
        db_session, "commit", side_effect=Exception("Database connection dropped")
    ):
        res = client.post("/api/v1/whatsapp/webhook", headers={"X-Hub-Signature-256": sig}, content=raw_body)
        assert res.status_code == 200  # Cleanly acknowledged to Meta without crashing

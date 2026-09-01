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
from app.models import Base, Conversation, Lead, Message


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


# ============================================================================
# GET Webhook Verification Tests
# ============================================================================


def test_get_webhook_verification_success(client):
    test_verify_token = "my_custom_verify_token_123"
    with patch("app.core.config.settings.WHATSAPP_VERIFY_TOKEN", test_verify_token):
        res = client.get(
            "/api/v1/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": test_verify_token,
                "hub.challenge": "1155998822",
            },
        )
        assert res.status_code == 200
        assert res.text == "1155998822"
        assert res.headers["content-type"].startswith("text/plain")


def test_get_webhook_verification_wrong_token(client):
    with patch("app.core.config.settings.WHATSAPP_VERIFY_TOKEN", "real_secret_token"):
        res = client.get(
            "/api/v1/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_attacker_token",
                "hub.challenge": "123456",
            },
        )
        assert res.status_code == 403
        assert "real_secret_token" not in res.text


def test_get_webhook_verification_wrong_mode(client):
    with patch("app.core.config.settings.WHATSAPP_VERIFY_TOKEN", "secret_token"):
        res = client.get(
            "/api/v1/whatsapp/webhook",
            params={
                "hub.mode": "publish",
                "hub.verify_token": "secret_token",
                "hub.challenge": "123456",
            },
        )
        assert res.status_code == 403


def test_get_webhook_verification_missing_server_token(client):
    with patch("app.core.config.settings.WHATSAPP_VERIFY_TOKEN", None):
        res = client.get(
            "/api/v1/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "any_token",
                "hub.challenge": "123456",
            },
        )
        assert res.status_code == 403


def test_get_webhook_verification_missing_params_fails_validation(client):
    res = client.get("/api/v1/whatsapp/webhook")
    assert res.status_code == 422


# ============================================================================
# POST Webhook Signature & HMAC-SHA256 Tests
# ============================================================================


def test_post_webhook_valid_signature_accepted(client):
    app_secret = "test_meta_app_secret_xyz_999"
    payload_dict = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID_100",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+923001234567",
                                "phone_number_id": "100000000000001",
                            },
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload_dict).encode("utf-8")
    valid_signature = generate_webhook_signature(raw_body, app_secret)

    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            headers={
                "X-Hub-Signature-256": valid_signature,
                "Content-Type": "application/json",
            },
            content=raw_body,
        )
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}


def test_post_webhook_missing_signature_rejected(client):
    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", "test_secret"):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            json={"object": "whatsapp_business_account"},
        )
        assert res.status_code == 403


def test_post_webhook_wrong_signature_rejected(client):
    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", "test_secret"):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": "sha256=" + "a" * 64},
            json={"object": "whatsapp_business_account"},
        )
        assert res.status_code == 403


def test_post_webhook_sha1_prefix_rejected(client):
    app_secret = "test_secret"
    raw_body = b'{"object":"whatsapp_business_account"}'
    valid_sha256 = generate_webhook_signature(raw_body, app_secret)
    sha1_prefixed = "sha1=" + valid_sha256.split("=")[1]

    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": sha1_prefixed},
            content=raw_body,
        )
        assert res.status_code == 403


def test_post_webhook_malformed_hex_signature_rejected(client):
    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", "test_secret"):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": "sha256=NOT_VALID_HEX_AT_ALL_ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"},
            content=b"{}",
        )
        assert res.status_code == 403


def test_post_webhook_wrong_length_signature_rejected(client):
    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", "test_secret"):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": "sha256=1234abcd"},
            content=b"{}",
        )
        assert res.status_code == 403


def test_post_webhook_empty_signature_header_rejected(client):
    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", "test_secret"):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": ""},
            content=b"{}",
        )
        assert res.status_code == 403


def test_post_webhook_missing_server_app_secret_returns_500(client):
    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", None):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": "sha256=" + "a" * 64},
            content=b"{}",
        )
        assert res.status_code == 500


def test_post_webhook_tampered_payload_rejected(client):
    app_secret = "test_meta_secret_123"
    original_payload = b'{"object": "whatsapp_business_account", "entry": []}'
    tampered_payload = b'{"object": "whatsapp_business_account", "entry": [], "extra": 1}'

    # Generate signature for original payload
    signature = generate_webhook_signature(original_payload, app_secret)

    # Send tampered payload with original signature -> MUST FAIL
    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": signature},
            content=tampered_payload,
        )
        assert res.status_code == 403


def test_invalid_signature_triggers_zero_database_writes(client, db_session):
    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", "test_secret"):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": "sha256=" + "f" * 64},
            content=b'{"object": "whatsapp_business_account", "entry": [{"messages": [{"text": "hello"}]}]}',
        )
        assert res.status_code == 403

    # Ensure zero CRM writes
    assert len(db_session.scalars(select(Lead)).all()) == 0
    assert len(db_session.scalars(select(Conversation)).all()) == 0
    assert len(db_session.scalars(select(Message)).all()) == 0


def test_post_webhook_does_not_require_jwt_or_clinic_id(client):
    app_secret = "meta_secret"
    payload = b'{"object": "whatsapp_business_account", "entry": []}'
    sig = generate_webhook_signature(payload, app_secret)

    # Note: No 'Authorization: Bearer' and no 'X-Clinic-ID' provided
    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": sig},
            content=payload,
        )
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}


def test_post_webhook_non_whatsapp_object_acknowledged_safely(client):
    app_secret = "meta_secret"
    payload = b'{"object": "page", "entry": []}'
    sig = generate_webhook_signature(payload, app_secret)

    with patch("app.core.config.settings.WHATSAPP_APP_SECRET", app_secret):
        res = client.post(
            "/api/v1/whatsapp/webhook",
            headers={"X-Hub-Signature-256": sig},
            content=payload,
        )
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}


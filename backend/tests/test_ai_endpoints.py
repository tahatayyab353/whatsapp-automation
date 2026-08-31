import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import AsyncMock, patch

from app.ai.exceptions import AIProviderTimeoutError
from app.ai.types import AIResponse
from app.core.security import create_access_token
from app.db.database import get_db
from app.main import app
from app.models import (
    Base,
    Clinic,
    ClinicMembership,
    Conversation,
    Message,
    User,
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


def test_ai_test_chat_endpoint_success_and_persistence(client, db_session):
    clinic = Clinic(name="AI Dental Clinic", slug="ai-dental", timezone="Asia/Karachi")
    staff = User(email="staff@ai.local", full_name="AI Staff", is_active=True)
    db_session.add_all([clinic, staff])
    db_session.commit()

    db_session.add(ClinicMembership(clinic_id=clinic.id, user_id=staff.id, role="staff"))
    conv = Conversation(clinic_id=clinic.id, channel="whatsapp", status="open")
    db_session.add(conv)
    db_session.commit()

    token = create_access_token(subject=str(staff.id))
    headers = {"Authorization": f"Bearer {token}", "X-Clinic-ID": str(clinic.id)}

    mock_ai_resp = AIResponse(
        content="Professional teeth whitening is PKR 15,000.",
        provider="gemini",
        model="gemini-1.5-flash",
    )

    with patch("app.ai.providers.gemini.GeminiProvider.generate", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = mock_ai_resp

        payload = {
            "conversation_id": str(conv.id),
            "message": "What is the price of teeth whitening?",
        }
        res = client.post("/api/v1/ai/test-chat", headers=headers, json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["content"] == "Professional teeth whitening is PKR 15,000."
        assert data["provider"] == "gemini"
        assert data["model"] == "gemini-1.5-flash"

    # Verify messages persisted in database (1 customer message + 1 AI message)
    persisted_msgs = db_session.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at.asc())
    ).all()

    assert len(persisted_msgs) == 2
    assert persisted_msgs[0].sender_type == "customer"
    assert persisted_msgs[0].content == "What is the price of teeth whitening?"
    assert persisted_msgs[1].sender_type == "ai"
    assert persisted_msgs[1].content == "Professional teeth whitening is PKR 15,000."


def test_ai_test_chat_endpoint_fallback_integration(client, db_session):
    clinic = Clinic(name="Fallback Clinic", slug="fb-clinic", timezone="Asia/Karachi")
    staff = User(email="staff@fb.local", full_name="Fallback Staff", is_active=True)
    db_session.add_all([clinic, staff])
    db_session.commit()

    db_session.add(ClinicMembership(clinic_id=clinic.id, user_id=staff.id, role="staff"))
    conv = Conversation(clinic_id=clinic.id, channel="whatsapp", status="open")
    db_session.add(conv)
    db_session.commit()

    token = create_access_token(subject=str(staff.id))
    headers = {"Authorization": f"Bearer {token}", "X-Clinic-ID": str(clinic.id)}

    mock_groq_resp = AIResponse(
        content="Responded via Groq fallback successfully.",
        provider="groq",
        model="llama-3.3-70b-versatile",
    )

    with patch("app.ai.providers.gemini.GeminiProvider.generate", side_effect=AIProviderTimeoutError("Gemini timed out", provider="gemini")):
        with patch("app.ai.providers.groq.GroqProvider.generate", new_callable=AsyncMock) as mock_groq:
            mock_groq.return_value = mock_groq_resp

            payload = {
                "conversation_id": str(conv.id),
                "message": "Are you open on weekends?",
            }
            res = client.post("/api/v1/ai/test-chat", headers=headers, json=payload)
            assert res.status_code == 200
            data = res.json()
            assert data["content"] == "Responded via Groq fallback successfully."
            assert data["provider"] == "groq"
            mock_groq.assert_called_once()


def test_ai_test_chat_endpoint_security_boundaries(client, db_session):
    clinic_a = Clinic(name="Clinic A", slug="clinic-a", timezone="Asia/Karachi")
    clinic_b = Clinic(name="Clinic B", slug="clinic-b", timezone="Asia/Karachi")
    staff_a = User(email="staff_a@test.local", full_name="Staff A", is_active=True)
    db_session.add_all([clinic_a, clinic_b, staff_a])
    db_session.commit()

    db_session.add(ClinicMembership(clinic_id=clinic_a.id, user_id=staff_a.id, role="staff"))
    conv_b = Conversation(clinic_id=clinic_b.id, channel="whatsapp", status="open")
    db_session.add(conv_b)
    db_session.commit()

    token_a = create_access_token(subject=str(staff_a.id))
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Clinic-ID": str(clinic_a.id)}

    # Attempt to chat on Clinic B conversation using Clinic A context -> 404 Not Found
    res = client.post(
        "/api/v1/ai/test-chat",
        headers=headers_a,
        json={"conversation_id": str(conv_b.id), "message": "Hello"},
    )
    assert res.status_code == 404

    # Unauthenticated request -> 401
    res_unauth = client.post(
        "/api/v1/ai/test-chat",
        headers={"X-Clinic-ID": str(clinic_a.id)},
        json={"conversation_id": str(conv_b.id), "message": "Hello"},
    )
    assert res_unauth.status_code == 401


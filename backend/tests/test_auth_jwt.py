import uuid
from datetime import datetime, timedelta, timezone
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token
from app.db.database import get_db
from app.main import app
from app.models import Base, User


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


def test_jwt_token_generation_and_claims():
    user_id = str(uuid.uuid4())
    token = create_access_token(subject=user_id)
    payload = decode_access_token(token)

    assert payload["sub"] == user_id
    assert "iat" in payload
    assert "exp" in payload
    assert "jti" in payload
    assert payload["exp"] > payload["iat"]

    # Verify no sensitive information leaked in token
    payload_str = str(payload).lower()
    for sensitive in ["password", "secret", "whatsapp", "phone", "postgres", "lead"]:
        assert sensitive not in payload_str


def test_valid_token_authentication(client, db_session):
    user = User(email="active@test.local", full_name="Active User", is_active=True)
    db_session.add(user)
    db_session.commit()

    token = create_access_token(subject=str(user.id))
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "active@test.local"
    assert "password_hash" not in data


def test_missing_token_returns_401(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "error" in response.json()


def test_malformed_token_returns_401(client):
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-valid-jwt-token"},
    )
    assert response.status_code == 401


def test_expired_token_returns_401(client, db_session):
    user = User(email="expired@test.local", full_name="Expired User", is_active=True)
    db_session.add(user)
    db_session.commit()

    expired_token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(seconds=-10),
    )
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401


def test_invalid_signature_returns_401(client, db_session):
    user = User(email="tampered@test.local", full_name="Tampered User", is_active=True)
    db_session.add(user)
    db_session.commit()

    fake_token = jwt.encode(
        {
            "sub": str(user.id),
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(minutes=10)).timestamp()),
            "jti": str(uuid.uuid4()),
        },
        "wrong-secret-key-that-does-not-match-at-least-32-chars!",
        algorithm=settings.JWT_ALGORITHM,
    )
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {fake_token}"},
    )
    assert response.status_code == 401


def test_missing_sub_returns_401(client):
    token_missing_sub = jwt.encode(
        {
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(minutes=10)).timestamp()),
            "jti": str(uuid.uuid4()),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_missing_sub}"},
    )
    assert response.status_code == 401


def test_inactive_user_returns_401(client, db_session):
    inactive_user = User(email="inactive@test.local", full_name="Inactive User", is_active=False)
    db_session.add(inactive_user)
    db_session.commit()

    token = create_access_token(subject=str(inactive_user.id))
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


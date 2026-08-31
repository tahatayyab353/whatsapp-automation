import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
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


def test_login_success(client, db_session):
    password = "StrongPassword123!"
    user = User(
        email="doctor@demo.local",
        full_name="Dr. Demo",
        password_hash=hash_password(password),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "doctor@demo.local", "password": password},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


def test_login_incorrect_password_fails_generic(client, db_session):
    user = User(
        email="doctor@demo.local",
        full_name="Dr. Demo",
        password_hash=hash_password("CorrectPassword123!"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "doctor@demo.local", "password": "WrongPassword123!"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["message"] == "Invalid email or password"


def test_login_unknown_email_fails_generic(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@demo.local", "password": "SomePassword123!"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["message"] == "Invalid email or password"


def test_login_inactive_user_fails(client, db_session):
    user = User(
        email="inactive@demo.local",
        full_name="Inactive Staff",
        password_hash=hash_password("ActivePassword123!"),
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@demo.local", "password": "ActivePassword123!"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["message"] == "Invalid email or password"


def test_login_malformed_email_fails_validation(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "ValidPassword123!"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_login_short_password_fails_validation(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "user@demo.local", "password": "123"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_user_me_never_exposes_password_hash(client, db_session):
    user = User(
        email="secure@demo.local",
        full_name="Secure User",
        password_hash=hash_password("SuperSecret123!"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "secure@demo.local", "password": "SuperSecret123!"},
    )
    token = login_res.json()["access_token"]

    me_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    data = me_res.json()
    assert "password_hash" not in data
    assert "password" not in data
    assert data["email"] == "secure@demo.local"


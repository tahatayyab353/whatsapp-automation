import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db.database import get_db
from app.main import app
from app.models import Base, Clinic, ClinicMembership, User


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


def test_multi_clinic_authorization_matrix(client, db_session):
    """
    Validates cross-clinic isolation and role differentiation:
    - User A: Clinic A (owner), Clinic B (staff)
    - User B: Clinic B (owner)
    """
    # 1. Setup Clinics
    clinic_a = Clinic(name="Clinic Alpha", slug="clinic-alpha", timezone="Asia/Karachi")
    clinic_b = Clinic(name="Clinic Beta", slug="clinic-beta", timezone="Asia/Karachi")
    db_session.add_all([clinic_a, clinic_b])
    db_session.commit()

    # 2. Setup Users
    user_a = User(
        email="user_a@test.local",
        full_name="User Alpha",
        password_hash=hash_password("Password123!"),
        is_active=True,
    )
    user_b = User(
        email="user_b@test.local",
        full_name="User Beta",
        password_hash=hash_password("Password123!"),
        is_active=True,
    )
    db_session.add_all([user_a, user_b])
    db_session.commit()

    # 3. Setup Memberships
    # User A -> Clinic A (owner), Clinic B (staff)
    mem_a_a = ClinicMembership(clinic_id=clinic_a.id, user_id=user_a.id, role="owner")
    mem_a_b = ClinicMembership(clinic_id=clinic_b.id, user_id=user_a.id, role="staff")

    # User B -> Clinic B (owner)
    mem_b_b = ClinicMembership(clinic_id=clinic_b.id, user_id=user_b.id, role="owner")

    db_session.add_all([mem_a_a, mem_a_b, mem_b_b])
    db_session.commit()

    token_a = create_access_token(subject=str(user_a.id))
    token_b = create_access_token(subject=str(user_b.id))

    # --- Scenario 1: User A + Clinic A (Owner) ---
    res = client.get(
        "/api/v1/auth/test-owner",
        headers={"Authorization": f"Bearer {token_a}", "X-Clinic-ID": str(clinic_a.id)},
    )
    assert res.status_code == 200
    assert res.json()["role"] == "owner"

    # --- Scenario 2: User A + Clinic B (Staff) ---
    # Allowed on basic clinic endpoint
    res_staff = client.get(
        "/api/v1/auth/test-clinic",
        headers={"Authorization": f"Bearer {token_a}", "X-Clinic-ID": str(clinic_b.id)},
    )
    assert res_staff.status_code == 200
    assert res_staff.json()["role"] == "staff"

    # DENIED on owner-only endpoint
    res_owner_denied = client.get(
        "/api/v1/auth/test-owner",
        headers={"Authorization": f"Bearer {token_a}", "X-Clinic-ID": str(clinic_b.id)},
    )
    assert res_owner_denied.status_code == 403

    # --- Scenario 3: User B + Clinic A (Non-member) ---
    # DENIED access completely because User B has no membership in Clinic A
    res_unauth_clinic = client.get(
        "/api/v1/auth/test-clinic",
        headers={"Authorization": f"Bearer {token_b}", "X-Clinic-ID": str(clinic_a.id)},
    )
    assert res_unauth_clinic.status_code == 403

    # --- Scenario 4: User B + Clinic B (Owner) ---
    res_b_owner = client.get(
        "/api/v1/auth/test-owner",
        headers={"Authorization": f"Bearer {token_b}", "X-Clinic-ID": str(clinic_b.id)},
    )
    assert res_b_owner.status_code == 200
    assert res_b_owner.json()["role"] == "owner"


def test_role_hierarchy_permissions(client, db_session):
    """
    Tests permissions for Owner, Admin, and Staff:
    - Owner: accesses owner, admin, staff
    - Admin: accesses admin, staff; blocked on owner
    - Staff: accesses staff; blocked on admin, owner
    """
    clinic = Clinic(name="Role Test Clinic", slug="role-test", timezone="Asia/Karachi")
    db_session.add(clinic)
    db_session.commit()

    owner_user = User(email="owner@role.local", full_name="Owner", is_active=True)
    admin_user = User(email="admin@role.local", full_name="Admin", is_active=True)
    staff_user = User(email="staff@role.local", full_name="Staff", is_active=True)
    db_session.add_all([owner_user, admin_user, staff_user])
    db_session.commit()

    db_session.add_all([
        ClinicMembership(clinic_id=clinic.id, user_id=owner_user.id, role="owner"),
        ClinicMembership(clinic_id=clinic.id, user_id=admin_user.id, role="admin"),
        ClinicMembership(clinic_id=clinic.id, user_id=staff_user.id, role="staff"),
    ])
    db_session.commit()

    owner_token = create_access_token(subject=str(owner_user.id))
    admin_token = create_access_token(subject=str(admin_user.id))
    staff_token = create_access_token(subject=str(staff_user.id))

    headers_owner = {"Authorization": f"Bearer {owner_token}", "X-Clinic-ID": str(clinic.id)}
    headers_admin = {"Authorization": f"Bearer {admin_token}", "X-Clinic-ID": str(clinic.id)}
    headers_staff = {"Authorization": f"Bearer {staff_token}", "X-Clinic-ID": str(clinic.id)}

    # Owner checks
    assert client.get("/api/v1/auth/test-owner", headers=headers_owner).status_code == 200
    assert client.get("/api/v1/auth/test-admin", headers=headers_owner).status_code == 200
    assert client.get("/api/v1/auth/test-clinic", headers=headers_owner).status_code == 200

    # Admin checks
    assert client.get("/api/v1/auth/test-owner", headers=headers_admin).status_code == 403
    assert client.get("/api/v1/auth/test-admin", headers=headers_admin).status_code == 200
    assert client.get("/api/v1/auth/test-clinic", headers=headers_admin).status_code == 200

    # Staff checks
    assert client.get("/api/v1/auth/test-owner", headers=headers_staff).status_code == 403
    assert client.get("/api/v1/auth/test-admin", headers=headers_staff).status_code == 403
    assert client.get("/api/v1/auth/test-clinic", headers=headers_staff).status_code == 200


def test_missing_x_clinic_id_header(client, db_session):
    user = User(email="user@header.local", full_name="User", is_active=True)
    db_session.add(user)
    db_session.commit()

    token = create_access_token(subject=str(user.id))
    response = client.get(
        "/api/v1/auth/test-clinic",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert "X-Clinic-ID" in response.json()["error"]["message"]


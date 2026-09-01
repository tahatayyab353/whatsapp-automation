import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.database import get_db
from app.integrations.whatsapp.client import WhatsAppClient
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
from app.services.whatsapp_service import whatsapp_service


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
def test_setup(db_session):
    # Clinic A
    clinic_a = Clinic(name="Clinic A Dental", slug="clinic-a", timezone="Asia/Karachi")
    owner_a = User(email="owner_a@test.local", full_name="Owner A", is_active=True)
    admin_a = User(email="admin_a@test.local", full_name="Admin A", is_active=True)
    staff_a = User(email="staff_a@test.local", full_name="Staff A", is_active=True)

    # Clinic B
    clinic_b = Clinic(name="Clinic B Aesthetics", slug="clinic-b", timezone="Asia/Karachi")
    owner_b = User(email="owner_b@test.local", full_name="Owner B", is_active=True)

    db_session.add_all([clinic_a, owner_a, admin_a, staff_a, clinic_b, owner_b])
    db_session.commit()

    db_session.add_all([
        ClinicMembership(clinic_id=clinic_a.id, user_id=owner_a.id, role="owner"),
        ClinicMembership(clinic_id=clinic_a.id, user_id=admin_a.id, role="admin"),
        ClinicMembership(clinic_id=clinic_a.id, user_id=staff_a.id, role="staff"),
        ClinicMembership(clinic_id=clinic_b.id, user_id=owner_b.id, role="owner"),
    ])
    db_session.commit()

    return {
        "clinic_a": clinic_a,
        "owner_a": owner_a,
        "admin_a": admin_a,
        "staff_a": staff_a,
        "clinic_b": clinic_b,
        "owner_b": owner_b,
    }


def test_create_whatsapp_account_roles_and_permissions(client, db_session, test_setup):
    clinic_a = test_setup["clinic_a"]
    owner_a = test_setup["owner_a"]
    admin_a = test_setup["admin_a"]
    staff_a = test_setup["staff_a"]

    secret_token = "EAA_SUPER_SECRET_PER_CLINIC_TOKEN_999"
    payload = {
        "phone_number": "+923001112233",
        "phone_number_id": "phone_id_12345",
        "business_account_id": "waba_id_67890",
        "display_name": "Clinic A Official",
        "access_token": secret_token,
    }

    # 1. Staff -> 403 Forbidden
    token_staff = create_access_token(subject=str(staff_a.id))
    res_staff = client.post(
        "/api/v1/whatsapp/accounts",
        headers={"Authorization": f"Bearer {token_staff}", "X-Clinic-ID": str(clinic_a.id)},
        json=payload,
    )
    assert res_staff.status_code == 403

    # 2. Admin -> 201 Created
    token_admin = create_access_token(subject=str(admin_a.id))
    res_admin = client.post(
        "/api/v1/whatsapp/accounts",
        headers={"Authorization": f"Bearer {token_admin}", "X-Clinic-ID": str(clinic_a.id)},
        json=payload,
    )
    assert res_admin.status_code == 201
    data_admin = res_admin.json()
    assert data_admin["phone_number"] == "+923001112233"
    assert data_admin["phone_number_id"] == "phone_id_12345"
    assert data_admin["display_name"] == "Clinic A Official"
    assert data_admin["is_active"] is True

    # Critical Security Check: Secret Access Token MUST NOT leak
    assert "access_token" not in data_admin
    assert secret_token not in res_admin.text

    # 3. Duplicate phone_number_id -> 400 Bad Request
    token_owner = create_access_token(subject=str(owner_a.id))
    res_dup = client.post(
        "/api/v1/whatsapp/accounts",
        headers={"Authorization": f"Bearer {token_owner}", "X-Clinic-ID": str(clinic_a.id)},
        json={
            "phone_number": "+923009998877",
            "phone_number_id": "phone_id_12345",  # already in use
        },
    )
    assert res_dup.status_code == 400


def test_get_and_list_whatsapp_accounts_secret_exclusion(client, db_session, test_setup):
    clinic_a = test_setup["clinic_a"]
    owner_a = test_setup["owner_a"]
    staff_a = test_setup["staff_a"]

    secret_token = "EAA_ANOTHER_SECRET_TOKEN_777"
    acc = WhatsAppAccount(
        clinic_id=clinic_a.id,
        phone_number="+923005556677",
        phone_number_id="phone_id_5556677",
        business_account_id="waba_id_555",
        display_name="Clinic A Reception",
        access_token=secret_token,
        is_active=True,
    )
    db_session.add(acc)
    db_session.commit()

    token_owner = create_access_token(subject=str(owner_a.id))
    headers_owner = {"Authorization": f"Bearer {token_owner}", "X-Clinic-ID": str(clinic_a.id)}

    # List Accounts
    res_list = client.get("/api/v1/whatsapp/accounts", headers=headers_owner)
    assert res_list.status_code == 200
    accounts = res_list.json()
    assert len(accounts) == 1
    assert accounts[0]["phone_number_id"] == "phone_id_5556677"
    assert "access_token" not in accounts[0]
    assert secret_token not in res_list.text

    # Get Single Account
    res_single = client.get(f"/api/v1/whatsapp/accounts/{acc.id}", headers=headers_owner)
    assert res_single.status_code == 200
    account_data = res_single.json()
    assert account_data["id"] == str(acc.id)
    assert "access_token" not in account_data
    assert secret_token not in res_single.text

    # Staff access -> 403 Forbidden
    token_staff = create_access_token(subject=str(staff_a.id))
    res_staff_list = client.get(
        "/api/v1/whatsapp/accounts",
        headers={"Authorization": f"Bearer {token_staff}", "X-Clinic-ID": str(clinic_a.id)},
    )
    assert res_staff_list.status_code == 403


def test_whatsapp_account_tenant_isolation(client, db_session, test_setup):
    clinic_a = test_setup["clinic_a"]
    owner_a = test_setup["owner_a"]
    clinic_b = test_setup["clinic_b"]
    owner_b = test_setup["owner_b"]

    acc_a = WhatsAppAccount(
        clinic_id=clinic_a.id,
        phone_number="+923001111111",
        phone_number_id="phone_id_clinic_a",
        is_active=True,
    )
    acc_b = WhatsAppAccount(
        clinic_id=clinic_b.id,
        phone_number="+923002222222",
        phone_number_id="phone_id_clinic_b",
        is_active=True,
    )
    db_session.add_all([acc_a, acc_b])
    db_session.commit()

    token_a = create_access_token(subject=str(owner_a.id))
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Clinic-ID": str(clinic_a.id)}

    token_b = create_access_token(subject=str(owner_b.id))
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Clinic-ID": str(clinic_b.id)}

    # Clinic A accesses Clinic A -> 200
    res_a = client.get(f"/api/v1/whatsapp/accounts/{acc_a.id}", headers=headers_a)
    assert res_a.status_code == 200

    # Clinic A attempts to access Clinic B -> 404 (does not leak existence)
    res_cross = client.get(f"/api/v1/whatsapp/accounts/{acc_b.id}", headers=headers_a)
    assert res_cross.status_code == 404

    # Clinic B attempts to patch Clinic A account -> 404
    res_patch_cross = client.patch(
        f"/api/v1/whatsapp/accounts/{acc_a.id}",
        headers=headers_b,
        json={"display_name": "Hacked Name"},
    )
    assert res_patch_cross.status_code == 404

    # Clinic B attempts to deactivate Clinic A account -> 404
    res_del_cross = client.delete(
        f"/api/v1/whatsapp/accounts/{acc_a.id}",
        headers=headers_b,
    )
    assert res_del_cross.status_code == 404


def test_whatsapp_token_update_semantics(client, db_session, test_setup):
    clinic_a = test_setup["clinic_a"]
    owner_a = test_setup["owner_a"]

    initial_token = "INITIAL_SECRET_TOKEN_111"
    acc = WhatsAppAccount(
        clinic_id=clinic_a.id,
        phone_number="+923003333333",
        phone_number_id="phone_id_semantics",
        display_name="Old Display Name",
        access_token=initial_token,
        is_active=True,
    )
    db_session.add(acc)
    db_session.commit()

    token_owner = create_access_token(subject=str(owner_a.id))
    headers_owner = {"Authorization": f"Bearer {token_owner}", "X-Clinic-ID": str(clinic_a.id)}

    # 1. Update display name WITHOUT providing access_token -> token is preserved
    res_patch1 = client.patch(
        f"/api/v1/whatsapp/accounts/{acc.id}",
        headers=headers_owner,
        json={"display_name": "New Display Name"},
    )
    assert res_patch1.status_code == 200
    assert "access_token" not in res_patch1.json()

    db_session.expire_all()
    updated_acc1 = db_session.scalar(select(WhatsAppAccount).where(WhatsAppAccount.id == acc.id))
    assert updated_acc1.display_name == "New Display Name"
    assert updated_acc1.access_token == initial_token  # Preserved

    # 2. Update WITH new token -> replaces token
    new_secret_token = "REPLACED_SECRET_TOKEN_222"
    res_patch2 = client.patch(
        f"/api/v1/whatsapp/accounts/{acc.id}",
        headers=headers_owner,
        json={"access_token": new_secret_token},
    )
    assert res_patch2.status_code == 200
    assert "access_token" not in res_patch2.json()
    assert new_secret_token not in res_patch2.text

    db_session.expire_all()
    updated_acc2 = db_session.scalar(select(WhatsAppAccount).where(WhatsAppAccount.id == acc.id))
    assert updated_acc2.access_token == new_secret_token  # Replaced


def test_whatsapp_deactivation_preserves_historical_data(client, db_session, test_setup):
    clinic_a = test_setup["clinic_a"]
    owner_a = test_setup["owner_a"]

    acc = WhatsAppAccount(
        clinic_id=clinic_a.id,
        phone_number="+923004444444",
        phone_number_id="phone_id_deactivation",
        is_active=True,
    )
    lead = Lead(
        clinic_id=clinic_a.id,
        full_name="Patient History",
        phone="+923004444444",
        status="active",
    )
    db_session.add_all([acc, lead])
    db_session.commit()

    conv = Conversation(
        clinic_id=clinic_a.id,
        lead_id=lead.id,
        channel="whatsapp",
        status="open",
    )
    db_session.add(conv)
    db_session.commit()

    msg = Message(
        clinic_id=clinic_a.id,
        conversation_id=conv.id,
        sender_type="customer",
        content="Important conversation history.",
    )
    db_session.add(msg)
    db_session.commit()

    token_owner = create_access_token(subject=str(owner_a.id))
    headers_owner = {"Authorization": f"Bearer {token_owner}", "X-Clinic-ID": str(clinic_a.id)}

    # Soft deactivate account via DELETE
    res_del = client.delete(f"/api/v1/whatsapp/accounts/{acc.id}", headers=headers_owner)
    assert res_del.status_code == 200

    db_session.expire_all()
    db_acc = db_session.scalar(select(WhatsAppAccount).where(WhatsAppAccount.id == acc.id))
    assert db_acc is not None
    assert db_acc.is_active is False

    # Historical Lead, Conversation, and Message records MUST remain intact
    db_lead = db_session.scalar(select(Lead).where(Lead.id == lead.id))
    db_conv = db_session.scalar(select(Conversation).where(Conversation.id == conv.id))
    db_msg = db_session.scalar(select(Message).where(Message.id == msg.id))

    assert db_lead is not None
    assert db_conv is not None
    assert db_msg is not None
    assert db_msg.content == "Important conversation history."


def test_internal_phone_number_id_lookup(db_session, test_setup):
    clinic_a = test_setup["clinic_a"]

    acc = WhatsAppAccount(
        clinic_id=clinic_a.id,
        phone_number="+923007778899",
        phone_number_id="meta_phone_id_9999",
        is_active=True,
    )
    db_session.add(acc)
    db_session.commit()

    # Valid active phone_number_id -> returns WhatsAppAccount
    found = whatsapp_service.get_account_by_phone_number_id(db_session, "meta_phone_id_9999")
    assert found is not None
    assert found.id == acc.id
    assert found.clinic_id == clinic_a.id

    # Unknown phone_number_id -> returns None
    unknown = whatsapp_service.get_account_by_phone_number_id(db_session, "non_existent_id")
    assert unknown is None

    # Inactive account -> returns None
    acc.is_active = False
    db_session.commit()
    inactive_lookup = whatsapp_service.get_account_by_phone_number_id(db_session, "meta_phone_id_9999")
    assert inactive_lookup is None


def test_whatsapp_client_foundation():
    client = WhatsAppClient(
        access_token="test_token_123",
        phone_number_id="123456789",
        api_version="v20.0",
    )
    assert client.base_url == "https://graph.facebook.com/v20.0/123456789"
    assert client.headers["Authorization"] == "Bearer test_token_123"
    assert client.headers["Content-Type"] == "application/json"


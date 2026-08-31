import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models import (
    Appointment,
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


@pytest.fixture(scope="function")
def db_session():
    """
    Creates a fresh isolated in-memory SQLite database session for unit testing models.
    """
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_clinic_creation_and_slug_uniqueness(db_session):
    clinic1 = Clinic(
        name="Clifton Dental Care",
        slug="clifton-dental",
        timezone="Asia/Karachi",
    )
    db_session.add(clinic1)
    db_session.commit()

    assert clinic1.id is not None
    assert clinic1.is_active is True
    assert clinic1.timezone == "Asia/Karachi"

    # Test slug uniqueness
    clinic2 = Clinic(
        name="Duplicate Slug Clinic",
        slug="clifton-dental",
        timezone="Asia/Karachi",
    )
    db_session.add(clinic2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_user_creation_and_email_uniqueness(db_session):
    user1 = User(
        email="doctor@test.local",
        full_name="Dr. Test User",
        password_hash=None,
    )
    db_session.add(user1)
    db_session.commit()

    assert user1.id is not None
    assert user1.is_active is True
    assert user1.is_platform_admin is False

    # Test email uniqueness
    user2 = User(
        email="doctor@test.local",
        full_name="Duplicate Email User",
    )
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_clinic_membership_constraints(db_session):
    clinic1 = Clinic(name="Clinic One", slug="clinic-1", timezone="Asia/Karachi")
    clinic2 = Clinic(name="Clinic Two", slug="clinic-2", timezone="Asia/Karachi")
    user = User(email="staff@test.local", full_name="Multi-Clinic Staff")
    db_session.add_all([clinic1, clinic2, user])
    db_session.commit()

    # User can join Clinic 1
    m1 = ClinicMembership(clinic_id=clinic1.id, user_id=user.id, role="owner")
    # User can join Clinic 2 (multi-tenant membership)
    m2 = ClinicMembership(clinic_id=clinic2.id, user_id=user.id, role="staff")
    db_session.add_all([m1, m2])
    db_session.commit()

    assert len(user.memberships) == 2

    # Cannot join same clinic twice
    duplicate_m = ClinicMembership(clinic_id=clinic1.id, user_id=user.id, role="admin")
    db_session.add(duplicate_m)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_lead_belongs_to_clinic(db_session):
    clinic = Clinic(name="Aesthetic Clinic", slug="aesthetic-clinic", timezone="Asia/Karachi")
    db_session.add(clinic)
    db_session.commit()

    lead = Lead(
        clinic_id=clinic.id,
        full_name="Sara Ahmed",
        phone="+923211234567",
        email="sara@example.com",
        source="whatsapp",
        status="new",
        service_interest="HydraFacial",
    )
    db_session.add(lead)
    db_session.commit()

    assert lead.id is not None
    assert lead.clinic_id == clinic.id
    assert lead.status == "new"
    assert lead.clinic.name == "Aesthetic Clinic"


def test_conversation_and_message_hierarchy(db_session):
    clinic = Clinic(name="Karachi Smiles", slug="karachi-smiles", timezone="Asia/Karachi")
    db_session.add(clinic)
    db_session.commit()

    lead = Lead(
        clinic_id=clinic.id,
        full_name="Bilal Shah",
        phone="+923331112233",
    )
    db_session.add(lead)
    db_session.commit()

    conv = Conversation(
        clinic_id=clinic.id,
        lead_id=lead.id,
        channel="whatsapp",
        external_conversation_id="+923331112233",
        status="open",
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(conv)
    db_session.commit()

    msg1 = Message(
        clinic_id=clinic.id,
        conversation_id=conv.id,
        sender_type="customer",
        message_type="text",
        content="Hello, what time do you open?",
    )
    msg2 = Message(
        clinic_id=clinic.id,
        conversation_id=conv.id,
        sender_type="ai",
        message_type="text",
        content="We open at 11:00 AM Monday through Saturday.",
    )
    db_session.add_all([msg1, msg2])
    db_session.commit()

    assert len(conv.messages) == 2
    assert conv.messages[0].content == "Hello, what time do you open?"
    assert conv.messages[1].sender_type == "ai"
    assert conv.messages[0].clinic_id == clinic.id


def test_appointment_scheduled_at_timezone(db_session):
    clinic = Clinic(name="Apex Dental", slug="apex-dental", timezone="Asia/Karachi")
    db_session.add(clinic)
    db_session.commit()

    scheduled_time = datetime(2026, 9, 15, 14, 30, tzinfo=timezone.utc)
    appointment = Appointment(
        clinic_id=clinic.id,
        scheduled_at=scheduled_time,
        status="confirmed",
        notes="Root canal stage 1",
    )
    db_session.add(appointment)
    db_session.commit()

    assert appointment.id is not None
    assert appointment.clinic_id == clinic.id
    assert appointment.status == "confirmed"
    assert appointment.scheduled_at.year == 2026
    assert appointment.scheduled_at.month == 9
    assert appointment.scheduled_at.day == 15
    assert appointment.scheduled_at.hour == 14
    assert appointment.scheduled_at.minute == 30


def test_knowledge_document_model(db_session):
    clinic = Clinic(name="Ortho Hub", slug="ortho-hub", timezone="Asia/Karachi")
    db_session.add(clinic)
    db_session.commit()

    doc = KnowledgeDocument(
        clinic_id=clinic.id,
        title="Braces vs Aligners Guide",
        category="service",
        content="Clear aligners are removable and virtually invisible...",
        is_active=True,
    )
    db_session.add(doc)
    db_session.commit()

    assert doc.id is not None
    assert doc.clinic_id == clinic.id
    assert doc.category == "service"
    assert doc.is_active is True


def test_whatsapp_account_phone_uniqueness(db_session):
    clinic1 = Clinic(name="Clinic A", slug="clinic-a", timezone="Asia/Karachi")
    clinic2 = Clinic(name="Clinic B", slug="clinic-b", timezone="Asia/Karachi")
    db_session.add_all([clinic1, clinic2])
    db_session.commit()

    wa1 = WhatsAppAccount(
        clinic_id=clinic1.id,
        phone_number="+923009998877",
        phone_number_id="WABA_1",
    )
    db_session.add(wa1)
    db_session.commit()

    # Same phone number cannot be assigned to another clinic
    wa2 = WhatsAppAccount(
        clinic_id=clinic2.id,
        phone_number="+923009998877",
        phone_number_id="WABA_2",
    )
    db_session.add(wa2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


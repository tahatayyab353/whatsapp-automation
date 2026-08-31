import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import (
    Appointment,
    Base,
    Clinic,
    Conversation,
    KnowledgeDocument,
    Lead,
    Message,
)


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_multi_tenant_isolation_pattern(db_session):
    """
    Demonstrates and validates the multi-tenant scoping access pattern.
    Ensures Clinic A and Clinic B records are strictly isolated by clinic_id.
    """
    # 1. Create two separate clinic tenants
    clinic_a = Clinic(name="Alpha Dental Clinic", slug="alpha-dental", timezone="Asia/Karachi")
    clinic_b = Clinic(name="Beta Aesthetic Center", slug="beta-aesthetics", timezone="Asia/Karachi")
    db_session.add_all([clinic_a, clinic_b])
    db_session.commit()

    # 2. Create tenant records for Clinic A
    lead_a = Lead(
        clinic_id=clinic_a.id,
        full_name="Patient Alpha",
        phone="+923001111111",
        service_interest="Dental Cleaning",
    )
    doc_a = KnowledgeDocument(
        clinic_id=clinic_a.id,
        title="Alpha Pricing",
        content="Cleaning: PKR 5,000",
    )
    conv_a = Conversation(
        clinic_id=clinic_a.id,
        channel="whatsapp",
        external_conversation_id="+923001111111",
        status="open",
        started_at=datetime.now(timezone.utc),
    )
    db_session.add_all([lead_a, doc_a, conv_a])
    db_session.flush()

    msg_a = Message(
        clinic_id=clinic_a.id,
        conversation_id=conv_a.id,
        sender_type="customer",
        content="Alpha inquiry message",
    )
    db_session.add(msg_a)

    # 3. Create tenant records for Clinic B
    lead_b = Lead(
        clinic_id=clinic_b.id,
        full_name="Patient Beta",
        phone="+923002222222",
        service_interest="Laser Skin Treatment",
    )
    doc_b = KnowledgeDocument(
        clinic_id=clinic_b.id,
        title="Beta Pricing",
        content="Laser: PKR 25,000",
    )
    conv_b = Conversation(
        clinic_id=clinic_b.id,
        channel="whatsapp",
        external_conversation_id="+923002222222",
        status="open",
        started_at=datetime.now(timezone.utc),
    )
    db_session.add_all([lead_b, doc_b, conv_b])
    db_session.flush()

    msg_b = Message(
        clinic_id=clinic_b.id,
        conversation_id=conv_b.id,
        sender_type="customer",
        content="Beta inquiry message",
    )
    db_session.add(msg_b)
    db_session.commit()

    # 4. Query with Clinic A Tenant Scope
    scoped_leads_a = db_session.scalars(
        select(Lead).where(Lead.clinic_id == clinic_a.id)
    ).all()
    scoped_docs_a = db_session.scalars(
        select(KnowledgeDocument).where(KnowledgeDocument.clinic_id == clinic_a.id)
    ).all()
    scoped_convs_a = db_session.scalars(
        select(Conversation).where(Conversation.clinic_id == clinic_a.id)
    ).all()
    scoped_msgs_a = db_session.scalars(
        select(Message).where(Message.clinic_id == clinic_a.id)
    ).all()

    # Verify Clinic A sees only Clinic A records
    assert len(scoped_leads_a) == 1
    assert scoped_leads_a[0].full_name == "Patient Alpha"
    assert scoped_leads_a[0].phone == "+923001111111"

    assert len(scoped_docs_a) == 1
    assert scoped_docs_a[0].title == "Alpha Pricing"

    assert len(scoped_convs_a) == 1
    assert scoped_convs_a[0].external_conversation_id == "+923001111111"

    assert len(scoped_msgs_a) == 1
    assert scoped_msgs_a[0].content == "Alpha inquiry message"

    # 5. Query with Clinic B Tenant Scope
    scoped_leads_b = db_session.scalars(
        select(Lead).where(Lead.clinic_id == clinic_b.id)
    ).all()
    scoped_docs_b = db_session.scalars(
        select(KnowledgeDocument).where(KnowledgeDocument.clinic_id == clinic_b.id)
    ).all()
    scoped_convs_b = db_session.scalars(
        select(Conversation).where(Conversation.clinic_id == clinic_b.id)
    ).all()
    scoped_msgs_b = db_session.scalars(
        select(Message).where(Message.clinic_id == clinic_b.id)
    ).all()

    # Verify Clinic B sees only Clinic B records
    assert len(scoped_leads_b) == 1
    assert scoped_leads_b[0].full_name == "Patient Beta"
    assert scoped_leads_b[0].phone == "+923002222222"

    assert len(scoped_docs_b) == 1
    assert scoped_docs_b[0].title == "Beta Pricing"

    assert len(scoped_convs_b) == 1
    assert scoped_convs_b[0].external_conversation_id == "+923002222222"

    assert len(scoped_msgs_b) == 1
    assert scoped_msgs_b[0].content == "Beta inquiry message"

    # 6. Verify cross-tenant isolation: No Clinic A record appears under Clinic B scope
    assert lead_b.id not in [l.id for l in scoped_leads_a]
    assert lead_a.id not in [l.id for l in scoped_leads_b]
    assert doc_b.id not in [d.id for d in scoped_docs_a]
    assert doc_a.id not in [d.id for d in scoped_docs_b]


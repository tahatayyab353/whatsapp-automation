import importlib
from sqlalchemy import create_engine, select
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
import scripts.seed_dev as seed_module


def test_seed_database_idempotency(monkeypatch):
    """
    Verifies that running the database seeder twice produces exactly the expected records without duplicates.
    """
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)

    # Monkeypatch SessionLocal in seed_dev to use the test SQLite database
    monkeypatch.setattr(seed_module, "SessionLocal", TestSession)

    # Run seed 1st time
    seed_module.seed_database()

    session = TestSession()
    clinics_count_1 = len(session.scalars(select(Clinic)).all())
    users_count_1 = len(session.scalars(select(User)).all())
    memberships_count_1 = len(session.scalars(select(ClinicMembership)).all())
    leads_count_1 = len(session.scalars(select(Lead)).all())
    convs_count_1 = len(session.scalars(select(Conversation)).all())
    msgs_count_1 = len(session.scalars(select(Message)).all())
    apps_count_1 = len(session.scalars(select(Appointment)).all())
    docs_count_1 = len(session.scalars(select(KnowledgeDocument)).all())
    wa_count_1 = len(session.scalars(select(WhatsAppAccount)).all())
    session.close()

    assert clinics_count_1 == 1
    assert users_count_1 == 3
    assert memberships_count_1 == 3
    assert leads_count_1 == 1
    assert convs_count_1 == 1
    assert msgs_count_1 == 3
    assert apps_count_1 == 1
    assert docs_count_1 == 3
    assert wa_count_1 == 1

    # Run seed 2nd time to verify idempotency (no duplicates created)
    seed_module.seed_database()

    session2 = TestSession()
    clinics_count_2 = len(session2.scalars(select(Clinic)).all())
    users_count_2 = len(session2.scalars(select(User)).all())
    memberships_count_2 = len(session2.scalars(select(ClinicMembership)).all())
    leads_count_2 = len(session2.scalars(select(Lead)).all())
    convs_count_2 = len(session2.scalars(select(Conversation)).all())
    msgs_count_2 = len(session2.scalars(select(Message)).all())
    apps_count_2 = len(session2.scalars(select(Appointment)).all())
    docs_count_2 = len(session2.scalars(select(KnowledgeDocument)).all())
    wa_count_2 = len(session2.scalars(select(WhatsAppAccount)).all())
    session2.close()

    assert clinics_count_2 == clinics_count_1
    assert users_count_2 == users_count_1
    assert memberships_count_2 == memberships_count_1
    assert leads_count_2 == leads_count_1
    assert convs_count_2 == convs_count_1
    assert msgs_count_2 == msgs_count_1
    assert apps_count_2 == apps_count_1
    assert docs_count_2 == docs_count_1
    assert wa_count_2 == wa_count_1

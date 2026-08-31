import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import AsyncMock

from app.ai.base import AIProvider
from app.ai.receptionist import ReceptionistService
from app.ai.types import AIResponse
from app.models import (
    Base,
    Clinic,
    Conversation,
    KnowledgeDocument,
    Lead,
    Message,
)


class MockProvider(AIProvider):
    def __init__(self):
        self.last_messages = []

    @property
    def provider_name(self) -> str:
        return "mock_gemini"

    @property
    def model_name(self) -> str:
        return "gemini-1.5-flash"

    async def generate(self, messages, *, temperature=0.2, max_tokens=500):
        self.last_messages = messages
        return AIResponse(
            content="Mock Receptionist Response",
            provider=self.provider_name,
            model=self.model_name,
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


@pytest.mark.anyio
async def test_receptionist_context_assembly_and_boundaries(db_session):
    clinic_a = Clinic(name="Clinic A", slug="clinic-a", timezone="Asia/Karachi")
    clinic_b = Clinic(name="Clinic B", slug="clinic-b", timezone="Asia/Karachi")
    db_session.add_all([clinic_a, clinic_b])
    db_session.commit()

    # Clinic A Active Knowledge
    doc_active = KnowledgeDocument(
        clinic_id=clinic_a.id,
        title="Active Treatment",
        content="Teeth cleaning costs PKR 5,000.",
        category="pricing",
        is_active=True,
    )
    # Clinic A Inactive Knowledge (Must be ignored)
    doc_inactive = KnowledgeDocument(
        clinic_id=clinic_a.id,
        title="Outdated Treatment",
        content="Old price PKR 1,000.",
        category="pricing",
        is_active=False,
    )
    # Clinic B Knowledge (Must NEVER appear in Clinic A prompt)
    doc_b = KnowledgeDocument(
        clinic_id=clinic_b.id,
        title="Clinic B Secret Policy",
        content="Free scaling for everyone.",
        category="pricing",
        is_active=True,
    )
    db_session.add_all([doc_active, doc_inactive, doc_b])
    db_session.commit()

    # Lead for Clinic A
    lead_a = Lead(
        clinic_id=clinic_a.id,
        full_name="Fatima Noor",
        phone="+923005556677",
        status="qualified",
        service_interest="Teeth Cleaning",
    )
    db_session.add(lead_a)
    db_session.commit()

    # Conversation for Clinic A
    conv_a = Conversation(
        clinic_id=clinic_a.id,
        lead_id=lead_a.id,
        channel="whatsapp",
        status="open",
    )
    db_session.add(conv_a)
    db_session.commit()

    # Existing message in Clinic A conversation
    msg_prev = Message(
        clinic_id=clinic_a.id,
        conversation_id=conv_a.id,
        sender_type="customer",
        message_type="text",
        content="Hello, is scaling painful?",
    )
    db_session.add(msg_prev)
    db_session.commit()

    provider = MockProvider()
    service = ReceptionistService(primary_provider=provider)

    res = await service.generate_receptionist_response(
        db=db_session,
        clinic=clinic_a,
        conversation=conv_a,
        customer_message_text="How much does it cost?",
    )

    assert res.content == "Mock Receptionist Response"

    # Analyze synthesized messages passed to model
    sent_messages = provider.last_messages
    assert len(sent_messages) >= 3  # System, Previous Customer Msg, New Customer Msg

    system_prompt = sent_messages[0]["content"]

    # 1. Active knowledge included
    assert "Active Treatment" in system_prompt
    assert "Teeth cleaning costs PKR 5,000." in system_prompt

    # 2. Inactive knowledge excluded
    assert "Outdated Treatment" not in system_prompt

    # 3. Cross-tenant knowledge excluded
    assert "Clinic B Secret Policy" not in system_prompt

    # 4. Lead context included
    assert "Fatima Noor" in system_prompt
    assert "+923005556677" in system_prompt
    assert "Teeth Cleaning" in system_prompt

    # 5. History included
    assert sent_messages[1]["role"] == "user"
    assert sent_messages[1]["content"] == "Hello, is scaling painful?"
    assert sent_messages[2]["role"] == "user"
    assert sent_messages[2]["content"] == "How much does it cost?"


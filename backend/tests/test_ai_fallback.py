import pytest
from unittest.mock import AsyncMock

from app.ai.base import AIProvider
from app.ai.exceptions import (
    AIAuthenticationError,
    AIProviderError,
    AIProviderTimeoutError,
    AIRateLimitError,
    AITemporaryServerError,
)
from app.ai.receptionist import ReceptionistService
from app.ai.types import AIResponse
from app.models import Clinic, Conversation


class DummyProvider(AIProvider):
    def __init__(self, name: str, model: str):
        self._name = name
        self._model = model
        self.generate_mock = AsyncMock()

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def model_name(self) -> str:
        return self._model

    async def generate(self, messages, *, temperature=0.2, max_tokens=500):
        return await self.generate_mock(messages, temperature=temperature, max_tokens=max_tokens)


@pytest.fixture
def dummy_clinic():
    return Clinic(name="Test Clinic", slug="test-clinic", timezone="Asia/Karachi")


@pytest.fixture
def dummy_conversation(dummy_clinic):
    return Conversation(clinic_id=dummy_clinic.id, channel="whatsapp", status="open")


@pytest.mark.anyio
async def test_primary_succeeds_fallback_not_invoked(dummy_clinic, dummy_conversation):
    mock_primary = DummyProvider("gemini", "gemini-1.5-flash")
    mock_fallback = DummyProvider("groq", "llama-3.3-70b-versatile")

    mock_primary.generate_mock.return_value = AIResponse(
        content="Primary Success",
        provider="gemini",
        model="gemini-1.5-flash",
    )

    service = ReceptionistService(primary_provider=mock_primary, fallback_provider=mock_fallback)

    # Empty DB mock since we test routing
    class DummyDB:
        def scalars(self, stmt):
            class Res:
                def all(self):
                    return []
            return Res()
        def scalar(self, stmt):
            return None

    res = await service.generate_receptionist_response(
        db=DummyDB(),
        clinic=dummy_clinic,
        conversation=dummy_conversation,
        customer_message_text="Hello",
    )

    assert res.content == "Primary Success"
    assert res.provider == "gemini"
    mock_primary.generate_mock.assert_called_once()
    mock_fallback.generate_mock.assert_not_called()


@pytest.mark.anyio
async def test_primary_timeout_triggers_fallback(dummy_clinic, dummy_conversation):
    mock_primary = DummyProvider("gemini", "gemini-1.5-flash")
    mock_fallback = DummyProvider("groq", "llama-3.3-70b-versatile")

    mock_primary.generate_mock.side_effect = AIProviderTimeoutError("Timeout", provider="gemini")
    mock_fallback.generate_mock.return_value = AIResponse(
        content="Fallback Success",
        provider="groq",
        model="llama-3.3-70b-versatile",
    )

    service = ReceptionistService(primary_provider=mock_primary, fallback_provider=mock_fallback)

    class DummyDB:
        def scalars(self, stmt):
            class Res:
                def all(self):
                    return []
            return Res()
        def scalar(self, stmt):
            return None

    res = await service.generate_receptionist_response(
        db=DummyDB(),
        clinic=dummy_clinic,
        conversation=dummy_conversation,
        customer_message_text="Hello",
    )

    assert res.content == "Fallback Success"
    assert res.provider == "groq"
    mock_primary.generate_mock.assert_called_once()
    mock_fallback.generate_mock.assert_called_once()


@pytest.mark.anyio
async def test_primary_rate_limit_triggers_fallback(dummy_clinic, dummy_conversation):
    mock_primary = DummyProvider("gemini", "gemini-1.5-flash")
    mock_fallback = DummyProvider("groq", "llama-3.3-70b-versatile")

    mock_primary.generate_mock.side_effect = AIRateLimitError("Rate limit", provider="gemini")
    mock_fallback.generate_mock.return_value = AIResponse(
        content="Groq RateLimit Fallback",
        provider="groq",
        model="llama-3.3-70b-versatile",
    )

    service = ReceptionistService(primary_provider=mock_primary, fallback_provider=mock_fallback)

    class DummyDB:
        def scalars(self, stmt):
            class Res:
                def all(self):
                    return []
            return Res()
        def scalar(self, stmt):
            return None

    res = await service.generate_receptionist_response(
        db=DummyDB(),
        clinic=dummy_clinic,
        conversation=dummy_conversation,
        customer_message_text="Hi",
    )
    assert res.provider == "groq"
    assert res.content == "Groq RateLimit Fallback"


@pytest.mark.anyio
async def test_primary_5xx_triggers_fallback(dummy_clinic, dummy_conversation):
    mock_primary = DummyProvider("gemini", "gemini-1.5-flash")
    mock_fallback = DummyProvider("groq", "llama-3.3-70b-versatile")

    mock_primary.generate_mock.side_effect = AITemporaryServerError("500 Server Error", provider="gemini")
    mock_fallback.generate_mock.return_value = AIResponse(
        content="Groq 500 Fallback",
        provider="groq",
        model="llama-3.3-70b-versatile",
    )

    service = ReceptionistService(primary_provider=mock_primary, fallback_provider=mock_fallback)

    class DummyDB:
        def scalars(self, stmt):
            class Res:
                def all(self):
                    return []
            return Res()
        def scalar(self, stmt):
            return None

    res = await service.generate_receptionist_response(
        db=DummyDB(),
        clinic=dummy_clinic,
        conversation=dummy_conversation,
        customer_message_text="Hi",
    )
    assert res.provider == "groq"
    assert res.content == "Groq 500 Fallback"


@pytest.mark.anyio
async def test_primary_auth_error_does_not_trigger_fallback(dummy_clinic, dummy_conversation):
    mock_primary = DummyProvider("gemini", "gemini-1.5-flash")
    mock_fallback = DummyProvider("groq", "llama-3.3-70b-versatile")

    mock_primary.generate_mock.side_effect = AIAuthenticationError("Invalid API Key", provider="gemini")

    service = ReceptionistService(primary_provider=mock_primary, fallback_provider=mock_fallback)

    class DummyDB:
        def scalars(self, stmt):
            class Res:
                def all(self):
                    return []
            return Res()
        def scalar(self, stmt):
            return None

    with pytest.raises(AIAuthenticationError):
        await service.generate_receptionist_response(
            db=DummyDB(),
            clinic=dummy_clinic,
            conversation=dummy_conversation,
            customer_message_text="Hi",
        )

    mock_primary.generate_mock.assert_called_once()
    mock_fallback.generate_mock.assert_not_called()


@pytest.mark.anyio
async def test_both_providers_fail_raises_exception(dummy_clinic, dummy_conversation):
    mock_primary = DummyProvider("gemini", "gemini-1.5-flash")
    mock_fallback = DummyProvider("groq", "llama-3.3-70b-versatile")

    mock_primary.generate_mock.side_effect = AIProviderTimeoutError("Gemini Timeout", provider="gemini")
    mock_fallback.generate_mock.side_effect = AIProviderTimeoutError("Groq Timeout", provider="groq")

    service = ReceptionistService(primary_provider=mock_primary, fallback_provider=mock_fallback)

    class DummyDB:
        def scalars(self, stmt):
            class Res:
                def all(self):
                    return []
            return Res()
        def scalar(self, stmt):
            return None

    with pytest.raises(AIProviderError):
        await service.generate_receptionist_response(
            db=DummyDB(),
            clinic=dummy_clinic,
            conversation=dummy_conversation,
            customer_message_text="Hi",
        )


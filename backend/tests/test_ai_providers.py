from typing import Any
import httpx
import pytest
from unittest.mock import AsyncMock, patch

from app.ai.exceptions import (
    AIAuthenticationError,
    AIConfigurationError,
    AIInvalidResponseError,
    AIProviderTimeoutError,
    AIRateLimitError,
    AITemporaryServerError,
)
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.groq import GroqProvider


@pytest.mark.anyio
async def test_gemini_provider_success():
    provider = GeminiProvider(api_key="test-key", model="gemini-1.5-flash")

    mock_json = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Hello! Teeth whitening starts at PKR 15,000."}],
                    "role": "model",
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 50,
            "candidatesTokenCount": 20,
            "totalTokenCount": 70,
        },
    }

    mock_response = httpx.Response(200, json=mock_json, request=httpx.Request("POST", "https://test"))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "How much for whitening?"}]
        res = await provider.generate(messages)

        assert res.content == "Hello! Teeth whitening starts at PKR 15,000."
        assert res.provider == "gemini"
        assert res.model == "gemini-1.5-flash"
        assert res.usage is not None
        assert res.usage.total_tokens == 70


@pytest.mark.anyio
async def test_gemini_provider_timeout_classified():
    provider = GeminiProvider(api_key="test-key", model="gemini-1.5-flash")

    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")):
        with pytest.raises(AIProviderTimeoutError) as exc_info:
            await provider.generate([{"role": "user", "content": "Hi"}])
        assert exc_info.value.retryable is True


@pytest.mark.anyio
async def test_gemini_provider_rate_limit_classified():
    provider = GeminiProvider(api_key="test-key", model="gemini-1.5-flash")

    mock_response = httpx.Response(429, json={"error": "Rate limit"}, request=httpx.Request("POST", "https://test"))
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        with pytest.raises(AIRateLimitError) as exc_info:
            await provider.generate([{"role": "user", "content": "Hi"}])
        assert exc_info.value.retryable is True


@pytest.mark.anyio
async def test_gemini_provider_server_error_classified():
    provider = GeminiProvider(api_key="test-key", model="gemini-1.5-flash")

    mock_response = httpx.Response(503, json={"error": "Overloaded"}, request=httpx.Request("POST", "https://test"))
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        with pytest.raises(AITemporaryServerError) as exc_info:
            await provider.generate([{"role": "user", "content": "Hi"}])
        assert exc_info.value.retryable is True


@pytest.mark.anyio
async def test_gemini_provider_auth_error_not_retryable():
    provider = GeminiProvider(api_key="test-key", model="gemini-1.5-flash")

    mock_response = httpx.Response(401, json={"error": "Invalid API Key"}, request=httpx.Request("POST", "https://test"))
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        with pytest.raises(AIAuthenticationError) as exc_info:
            await provider.generate([{"role": "user", "content": "Hi"}])
        assert exc_info.value.retryable is False


@pytest.mark.anyio
async def test_gemini_provider_missing_key():
    provider = GeminiProvider(api_key=None, model="gemini-1.5-flash")
    with patch("app.core.config.settings.GEMINI_API_KEY", None):
        with pytest.raises(AIConfigurationError):
            await provider.generate([{"role": "user", "content": "Hi"}])


@pytest.mark.anyio
async def test_groq_provider_success():
    provider = GroqProvider(api_key="groq-test-key", model="llama-3.3-70b-versatile")

    mock_json = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Hello from Groq! We are open Monday to Saturday.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 40,
            "completion_tokens": 15,
            "total_tokens": 55,
        },
    }

    mock_response = httpx.Response(200, json=mock_json, request=httpx.Request("POST", "https://test"))
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        res = await provider.generate([{"role": "user", "content": "What are your hours?"}])
        assert res.content == "Hello from Groq! We are open Monday to Saturday."
        assert res.provider == "groq"
        assert res.model == "llama-3.3-70b-versatile"
        assert res.usage is not None
        assert res.usage.total_tokens == 55


@pytest.mark.anyio
async def test_groq_provider_timeout():
    provider = GroqProvider(api_key="groq-test-key", model="llama-3.3-70b-versatile")

    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")):
        with pytest.raises(AIProviderTimeoutError):
            await provider.generate([{"role": "user", "content": "Hi"}])


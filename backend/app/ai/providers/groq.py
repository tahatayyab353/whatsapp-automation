from typing import Any, Dict, List, Optional
import httpx

from app.ai.base import AIProvider
from app.ai.exceptions import (
    AIAuthenticationError,
    AIConfigurationError,
    AIInvalidResponseError,
    AIProviderError,
    AIProviderTimeoutError,
    AIRateLimitError,
    AITemporaryServerError,
)
from app.ai.types import AIResponse, AIUsage
from app.core.config import settings


class GroqProvider(AIProvider):
    """
    Groq AI Provider implementing OpenAI-compatible Chat Completions REST API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self._api_key = api_key or settings.GROQ_API_KEY
        self._model = model or settings.GROQ_MODEL
        self._timeout = timeout or settings.AI_REQUEST_TIMEOUT_SECONDS

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self._model

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 500,
    ) -> AIResponse:
        if not self._api_key:
            raise AIConfigurationError(
                "Groq API key is not configured.",
                provider=self.provider_name,
            )

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise AIProviderTimeoutError(
                f"Groq request timed out after {self._timeout}s",
                provider=self.provider_name,
            ) from exc
        except httpx.RequestError as exc:
            raise AITemporaryServerError(
                f"Groq connection error: {str(exc)}",
                provider=self.provider_name,
            ) from exc

        if response.status_code == 401 or response.status_code == 403:
            raise AIAuthenticationError(
                "Groq authentication failed. Invalid API Key.",
                provider=self.provider_name,
            )
        elif response.status_code == 429:
            raise AIRateLimitError(
                "Groq rate limit exceeded.",
                provider=self.provider_name,
            )
        elif response.status_code >= 500:
            raise AITemporaryServerError(
                f"Groq temporary server error ({response.status_code}).",
                provider=self.provider_name,
            )
        elif response.status_code != 200:
            raise AIProviderError(
                f"Groq API returned error status {response.status_code}.",
                provider=self.provider_name,
            )

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise AIInvalidResponseError(
                "Groq returned no choices in completion response.",
                provider=self.provider_name,
            )

        first_choice = choices[0]
        msg_obj = first_choice.get("message", {})
        generated_text = msg_obj.get("content", "").strip()
        if not generated_text:
            raise AIInvalidResponseError(
                "Groq completion message is empty.",
                provider=self.provider_name,
            )

        # Extract usage metrics if available
        usage_data = data.get("usage", {})
        usage: Optional[AIUsage] = None
        if usage_data:
            usage = AIUsage(
                input_tokens=usage_data.get("prompt_tokens"),
                output_tokens=usage_data.get("completion_tokens"),
                total_tokens=usage_data.get("total_tokens"),
            )

        return AIResponse(
            content=generated_text,
            provider=self.provider_name,
            model=self._model,
            usage=usage,
        )


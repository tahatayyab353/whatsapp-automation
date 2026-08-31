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


class GeminiProvider(AIProvider):
    """
    Google Gemini AI Provider implementing generateContent via official REST API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self._api_key = api_key or settings.GEMINI_API_KEY
        self._model = model or settings.GEMINI_MODEL
        self._timeout = timeout or settings.AI_REQUEST_TIMEOUT_SECONDS

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    def _build_payload(
        self,
        messages: List[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        system_instruction_text = ""
        contents = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                if system_instruction_text:
                    system_instruction_text += "\n\n" + content
                else:
                    system_instruction_text = content
            elif role == "user":
                contents.append({
                    "role": "user",
                    "parts": [{"text": content}],
                })
            elif role in ("assistant", "model"):
                contents.append({
                    "role": "model",
                    "parts": [{"text": content}],
                })

        # Ensure at least one content entry exists
        if not contents:
            contents.append({"role": "user", "parts": [{"text": "Hello"}]})

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        if system_instruction_text:
            payload["system_instruction"] = {
                "parts": [{"text": system_instruction_text}]
            }

        return payload

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 500,
    ) -> AIResponse:
        if not self._api_key:
            raise AIConfigurationError(
                "Gemini API key is not configured.",
                provider=self.provider_name,
            )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent?key={self._api_key}"
        payload = self._build_payload(messages, temperature, max_tokens)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise AIProviderTimeoutError(
                f"Gemini request timed out after {self._timeout}s",
                provider=self.provider_name,
            ) from exc
        except httpx.RequestError as exc:
            raise AITemporaryServerError(
                f"Gemini connection error: {str(exc)}",
                provider=self.provider_name,
            ) from exc

        if response.status_code == 401 or response.status_code == 403:
            raise AIAuthenticationError(
                "Gemini authentication failed. Invalid API Key or permissions.",
                provider=self.provider_name,
            )
        elif response.status_code == 429:
            raise AIRateLimitError(
                "Gemini rate limit exceeded.",
                provider=self.provider_name,
            )
        elif response.status_code >= 500:
            raise AITemporaryServerError(
                f"Gemini temporary server error ({response.status_code}).",
                provider=self.provider_name,
            )
        elif response.status_code != 200:
            raise AIProviderError(
                f"Gemini API returned error status {response.status_code}.",
                provider=self.provider_name,
            )

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            prompt_feedback = data.get("promptFeedback", {})
            block_reason = prompt_feedback.get("blockReason", "Unknown")
            raise AIInvalidResponseError(
                f"Gemini returned no candidates (blockReason: {block_reason}).",
                provider=self.provider_name,
            )

        first_candidate = candidates[0]
        content_obj = first_candidate.get("content", {})
        parts = content_obj.get("parts", [])
        if not parts or "text" not in parts[0]:
            raise AIInvalidResponseError(
                "Gemini response candidate contains no text.",
                provider=self.provider_name,
            )

        generated_text = parts[0]["text"].strip()

        # Extract usage metrics if available
        usage_data = data.get("usageMetadata", {})
        usage: Optional[AIUsage] = None
        if usage_data:
            usage = AIUsage(
                input_tokens=usage_data.get("promptTokenCount"),
                output_tokens=usage_data.get("candidatesTokenCount"),
                total_tokens=usage_data.get("totalTokenCount"),
            )

        return AIResponse(
            content=generated_text,
            provider=self.provider_name,
            model=self._model,
            usage=usage,
        )


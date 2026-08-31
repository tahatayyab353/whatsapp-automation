from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from app.ai.types import AIResponse


class AIProvider(ABC):
    """
    Abstract Base Class for AI model providers (Gemini, Groq, etc.).
    Exposes a standardized, async interface for multi-turn chat completion.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the canonical name of the provider (e.g. 'gemini', 'groq')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Returns the active model name used by this provider instance."""
        pass

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 500,
    ) -> AIResponse:
        """
        Executes an async completion call to the provider.

        Args:
            messages: List of message dicts (e.g. [{'role': 'system'|'user'|'assistant', 'content': '...'}]).
            temperature: Sampling temperature (0.0 to 1.0).
            max_tokens: Maximum output tokens to generate.

        Returns:
            Normalized AIResponse containing generated content, provider, model, and optional usage.

        Raises:
            AIProviderError or specific subclass on failure.
        """
        pass


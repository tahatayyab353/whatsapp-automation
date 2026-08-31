from typing import Optional
from app.ai.base import AIProvider
from app.ai.exceptions import AIConfigurationError
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.groq import GroqProvider
from app.core.config import settings


def get_provider(provider_name: str) -> AIProvider:
    """
    Instantiates an AI provider instance based on provider name.
    """
    clean_name = provider_name.lower().strip()
    if clean_name == "gemini":
        return GeminiProvider()
    elif clean_name == "groq":
        return GroqProvider()
    else:
        raise AIConfigurationError(f"Unsupported AI provider: '{provider_name}'.")


def get_primary_provider() -> AIProvider:
    """
    Returns the configured primary AI provider instance (default: Gemini).
    """
    provider_name = settings.AI_PROVIDER or "gemini"
    return get_provider(provider_name)


def get_fallback_provider() -> Optional[AIProvider]:
    """
    Returns the designated fallback AI provider instance (default: Groq).
    """
    primary_name = (settings.AI_PROVIDER or "gemini").lower().strip()
    if primary_name == "gemini":
        return GroqProvider()
    elif primary_name == "groq":
        return GeminiProvider()
    return None


class AIProviderError(Exception):
    """Base exception for all AI provider interactions."""

    def __init__(self, message: str, provider: str = "unknown", retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.retryable = retryable


class AIProviderTimeoutError(AIProviderError):
    """Raised when an AI provider request times out (retryable)."""

    def __init__(self, message: str = "AI provider request timed out", provider: str = "unknown"):
        super().__init__(message, provider=provider, retryable=True)


class AIRateLimitError(AIProviderError):
    """Raised when an AI provider rate limit (HTTP 429) is encountered (retryable)."""

    def __init__(self, message: str = "AI provider rate limit exceeded", provider: str = "unknown"):
        super().__init__(message, provider=provider, retryable=True)


class AITemporaryServerError(AIProviderError):
    """Raised when an AI provider returns a 5xx server error or temporary outage (retryable)."""

    def __init__(self, message: str = "AI provider encountered a temporary server error", provider: str = "unknown"):
        super().__init__(message, provider=provider, retryable=True)


class AIAuthenticationError(AIProviderError):
    """Raised when provider authentication fails due to invalid API keys (non-retryable)."""

    def __init__(self, message: str = "AI provider authentication failed", provider: str = "unknown"):
        super().__init__(message, provider=provider, retryable=False)


class AIConfigurationError(AIProviderError):
    """Raised when required provider configuration or API keys are missing (non-retryable)."""

    def __init__(self, message: str = "AI provider is not configured properly", provider: str = "unknown"):
        super().__init__(message, provider=provider, retryable=False)


class AIInvalidResponseError(AIProviderError):
    """Raised when provider returns an empty, blocked, or unparseable response."""

    def __init__(self, message: str = "AI provider returned an invalid response", provider: str = "unknown"):
        super().__init__(message, provider=provider, retryable=False)


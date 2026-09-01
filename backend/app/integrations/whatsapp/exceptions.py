class WhatsAppIntegrationError(Exception):
    """Base exception for all WhatsApp Cloud API integration failures."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class WhatsAppAuthenticationError(WhatsAppIntegrationError):
    """Raised when WhatsApp Cloud API authentication fails (invalid or expired token)."""

    def __init__(self, message: str = "WhatsApp Cloud API authentication failed"):
        super().__init__(message, status_code=401)


class WhatsAppRateLimitError(WhatsAppIntegrationError):
    """Raised when Meta rate limits are reached (HTTP 429)."""

    def __init__(self, message: str = "WhatsApp Cloud API rate limit exceeded"):
        super().__init__(message, status_code=429)


class WhatsAppNetworkError(WhatsAppIntegrationError):
    """Raised when a network timeout or connection error occurs communicating with Meta."""

    def __init__(self, message: str = "Network error connecting to Meta Graph API"):
        super().__init__(message, status_code=503)


class WhatsAppAPIError(WhatsAppIntegrationError):
    """Raised when Meta returns a structured error payload."""

    def __init__(self, message: str, meta_code: int = 0, status_code: int = 400):
        super().__init__(message, status_code=status_code)
        self.meta_code = meta_code


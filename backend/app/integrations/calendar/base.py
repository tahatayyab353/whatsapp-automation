from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class CalendarProviderError(Exception):
    """Base exception for calendar provider operations."""
    def __init__(self, message: str, provider: str, retryable: bool = False, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.retryable = retryable
        self.status_code = status_code


class CalendarAuthError(CalendarProviderError):
    """Raised when authentication/token exchange fails or token is expired/revoked."""
    def __init__(self, message: str, provider: str, status_code: Optional[int] = 401):
        super().__init__(message, provider=provider, retryable=False, status_code=status_code)


class CalendarRateLimitError(CalendarProviderError):
    """Raised when external calendar API rate limit is exceeded."""
    def __init__(self, message: str, provider: str, status_code: Optional[int] = 429):
        super().__init__(message, provider=provider, retryable=True, status_code=status_code)


class CalendarProvider(ABC):
    """
    Abstract interface for external calendar providers (Google Calendar, Microsoft Graph).
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the canonical provider name ('google', 'microsoft')."""
        pass

    @abstractmethod
    def get_authorization_url(self, state: str) -> str:
        """Generates the OAuth 2.0 authorization URL with the secure CSRF state."""
        pass

    @abstractmethod
    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """
        Exchanges authorization code for access_token, refresh_token, token_expires_at, and account_identifier.
        """
        pass

    @abstractmethod
    async def refresh_tokens(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refreshes expired access token using the refresh_token.
        Returns dict with new access_token, optional new refresh_token, and token_expires_at.
        """
        pass

    @abstractmethod
    async def list_calendars(self, access_token: str) -> List[Dict[str, str]]:
        """
        Lists calendars accessible by the authenticated user/account.
        Returns list of dicts with 'id', 'name', 'primary' (bool).
        """
        pass

    @abstractmethod
    async def create_event(
        self,
        access_token: str,
        calendar_id: str,
        event_data: Dict[str, Any],
    ) -> str:
        """
        Creates an external calendar event.
        Returns the external event ID.
        """
        pass

    @abstractmethod
    async def update_event(
        self,
        access_token: str,
        calendar_id: str,
        event_id: str,
        event_data: Dict[str, Any],
    ) -> None:
        """
        Updates an existing external calendar event.
        """
        pass

    @abstractmethod
    async def delete_event(
        self,
        access_token: str,
        calendar_id: str,
        event_id: str,
    ) -> None:
        """
        Deletes or marks cancelled the external calendar event.
        """
        pass

    @abstractmethod
    async def get_event(
        self,
        access_token: str,
        calendar_id: str,
        event_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves an external calendar event by ID. Returns None if not found.
        """
        pass

    @abstractmethod
    async def validate_connection(self, access_token: str) -> bool:
        """
        Validates whether current credentials can communicate with the provider.
        """
        pass


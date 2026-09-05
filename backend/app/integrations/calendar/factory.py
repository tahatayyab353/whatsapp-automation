from app.core.exceptions import BadRequestException
from app.integrations.calendar.base import CalendarProvider
from app.integrations.calendar.google import GoogleCalendarProvider
from app.integrations.calendar.microsoft import MicrosoftCalendarProvider


def get_calendar_provider(provider_name: str) -> CalendarProvider:
    """
    Factory resolving the appropriate CalendarProvider adapter.
    """
    name = (provider_name or "").lower().strip()
    if name == "google":
        return GoogleCalendarProvider()
    elif name in ("microsoft", "outlook", "office365"):
        return MicrosoftCalendarProvider()
    else:
        raise BadRequestException(f"Unsupported calendar provider '{provider_name}'. Supported: 'google', 'microsoft'")


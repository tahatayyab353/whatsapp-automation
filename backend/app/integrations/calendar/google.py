from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import urllib.parse
import httpx

from app.core.config import settings
from app.integrations.calendar.base import (
    CalendarAuthError,
    CalendarProvider,
    CalendarProviderError,
    CalendarRateLimitError,
)


class GoogleCalendarProvider(CalendarProvider):
    """
    Official Google Calendar REST API integration.
    Supports OAuth 2.0 authorization, token exchange/refresh, calendar discovery,
    and timezone-aware appointment event synchronization.
    """

    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
    SCOPES = [
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/userinfo.email",
    ]

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.client_id = client_id or settings.GOOGLE_CLIENT_ID or ""
        self.client_secret = client_secret or settings.GOOGLE_CLIENT_SECRET or ""
        self.redirect_uri = redirect_uri or settings.GOOGLE_REDIRECT_URI
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        return "google"

    def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{self.AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def exchange_code(self, code: str) -> Dict[str, Any]:
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.TOKEN_URL, data=payload)
            if resp.status_code == 400 or resp.status_code == 401:
                raise CalendarAuthError(
                    f"Google token exchange failed: {resp.text}",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                )
            elif resp.status_code != 200:
                raise CalendarProviderError(
                    f"Google token exchange error ({resp.status_code}): {resp.text}",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                    retryable=resp.status_code >= 500,
                )

            data = resp.json()
            access_token = data.get("access_token")
            refresh_token = data.get("refresh_token")
            expires_in = data.get("expires_in", 3600)
            token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            # Retrieve account email
            account_identifier: Optional[str] = None
            try:
                user_resp = await client.get(
                    self.USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if user_resp.status_code == 200:
                    account_identifier = user_resp.json().get("email")
            except Exception:
                pass

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_expires_at": token_expires_at,
                "account_identifier": account_identifier or "google_account",
            }

    async def refresh_tokens(self, refresh_token: str) -> Dict[str, Any]:
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.TOKEN_URL, data=payload)
            if resp.status_code in (400, 401):
                raise CalendarAuthError(
                    f"Google token refresh failed: {resp.text}",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                )
            elif resp.status_code != 200:
                raise CalendarProviderError(
                    f"Google token refresh error ({resp.status_code}): {resp.text}",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                    retryable=resp.status_code >= 500,
                )

            data = resp.json()
            access_token = data.get("access_token")
            new_refresh_token = data.get("refresh_token") or refresh_token
            expires_in = data.get("expires_in", 3600)
            token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            return {
                "access_token": access_token,
                "refresh_token": new_refresh_token,
                "token_expires_at": token_expires_at,
            }

    async def list_calendars(self, access_token: str) -> List[Dict[str, Any]]:
        url = f"{self.CALENDAR_API_BASE}/users/me/calendarList"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code in (401, 403):
                raise CalendarAuthError(
                    "Google Calendar list authentication failed.",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                )
            elif resp.status_code == 429:
                raise CalendarRateLimitError(
                    "Google Calendar rate limit exceeded.",
                    provider=self.provider_name,
                )
            elif resp.status_code != 200:
                raise CalendarProviderError(
                    f"Google Calendar list error ({resp.status_code})",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                    retryable=resp.status_code >= 500,
                )

            data = resp.json()
            items = data.get("items", [])
            calendars = []
            for item in items:
                calendars.append({
                    "id": item.get("id"),
                    "name": item.get("summary", "Untitled Calendar"),
                    "primary": bool(item.get("primary", False)),
                    "description": item.get("description"),
                })
            return calendars

    async def create_event(
        self,
        access_token: str,
        calendar_id: str,
        event_data: Dict[str, Any],
    ) -> str:
        cal_id = urllib.parse.quote(calendar_id or "primary", safe="")
        url = f"{self.CALENDAR_API_BASE}/calendars/{cal_id}/events"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Format timezone-aware start and end
        payload = {
            "summary": event_data.get("summary", "Appointment"),
            "description": event_data.get("description", ""),
            "start": {
                "dateTime": event_data.get("start_time"),
                "timeZone": event_data.get("timezone", "Asia/Karachi"),
            },
            "end": {
                "dateTime": event_data.get("end_time"),
                "timeZone": event_data.get("timezone", "Asia/Karachi"),
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code in (401, 403):
                raise CalendarAuthError(
                    "Google Calendar event creation unauthorized.",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                )
            elif resp.status_code == 429:
                raise CalendarRateLimitError(
                    "Google Calendar rate limit exceeded during event creation.",
                    provider=self.provider_name,
                )
            elif resp.status_code != 200:
                raise CalendarProviderError(
                    f"Google Calendar create event error ({resp.status_code}): {resp.text}",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                    retryable=resp.status_code >= 500,
                )

            return resp.json().get("id")

    async def update_event(
        self,
        access_token: str,
        calendar_id: str,
        event_id: str,
        event_data: Dict[str, Any],
    ) -> None:
        cal_id = urllib.parse.quote(calendar_id or "primary", safe="")
        evt_id = urllib.parse.quote(event_id, safe="")
        url = f"{self.CALENDAR_API_BASE}/calendars/{cal_id}/events/{evt_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "summary": event_data.get("summary", "Appointment"),
            "description": event_data.get("description", ""),
            "start": {
                "dateTime": event_data.get("start_time"),
                "timeZone": event_data.get("timezone", "Asia/Karachi"),
            },
            "end": {
                "dateTime": event_data.get("end_time"),
                "timeZone": event_data.get("timezone", "Asia/Karachi"),
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.patch(url, headers=headers, json=payload)
            if resp.status_code in (401, 403):
                raise CalendarAuthError(
                    "Google Calendar event update unauthorized.",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                )
            elif resp.status_code == 429:
                raise CalendarRateLimitError(
                    "Google Calendar rate limit exceeded during event update.",
                    provider=self.provider_name,
                )
            elif resp.status_code != 200:
                raise CalendarProviderError(
                    f"Google Calendar update event error ({resp.status_code}): {resp.text}",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                    retryable=resp.status_code >= 500,
                )

    async def delete_event(
        self,
        access_token: str,
        calendar_id: str,
        event_id: str,
    ) -> None:
        cal_id = urllib.parse.quote(calendar_id or "primary", safe="")
        evt_id = urllib.parse.quote(event_id, safe="")
        url = f"{self.CALENDAR_API_BASE}/calendars/{cal_id}/events/{evt_id}"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.delete(url, headers=headers)
            if resp.status_code in (401, 403):
                raise CalendarAuthError(
                    "Google Calendar event delete unauthorized.",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                )
            elif resp.status_code == 429:
                raise CalendarRateLimitError(
                    "Google Calendar rate limit exceeded during event deletion.",
                    provider=self.provider_name,
                )
            elif resp.status_code not in (200, 204, 404, 410):
                # 404/410 means event is already deleted, which is safe/idempotent
                raise CalendarProviderError(
                    f"Google Calendar delete event error ({resp.status_code}): {resp.text}",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                    retryable=resp.status_code >= 500,
                )

    async def get_event(
        self,
        access_token: str,
        calendar_id: str,
        event_id: str,
    ) -> Optional[Dict[str, Any]]:
        cal_id = urllib.parse.quote(calendar_id or "primary", safe="")
        evt_id = urllib.parse.quote(event_id, safe="")
        url = f"{self.CALENDAR_API_BASE}/calendars/{cal_id}/events/{evt_id}"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 404 or resp.status_code == 410:
                return None
            elif resp.status_code in (401, 403):
                raise CalendarAuthError(
                    "Google Calendar get event unauthorized.",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                )
            elif resp.status_code != 200:
                raise CalendarProviderError(
                    f"Google Calendar get event error ({resp.status_code})",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                    retryable=resp.status_code >= 500,
                )
            return resp.json()

    async def validate_connection(self, access_token: str) -> bool:
        try:
            calendars = await self.list_calendars(access_token)
            return bool(calendars is not None)
        except Exception:
            return False


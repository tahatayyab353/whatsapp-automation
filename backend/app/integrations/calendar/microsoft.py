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


class MicrosoftCalendarProvider(CalendarProvider):
    """
    Microsoft 365 / Outlook Calendar integration via Microsoft Graph API v1.0.
    Supports OAuth 2.0 authorization, token exchange/refresh, calendar discovery,
    and timezone-aware appointment event synchronization.
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
    SCOPES = [
        "offline_access",
        "Calendars.ReadWrite",
        "User.Read",
    ]

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        tenant_id: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.client_id = client_id or settings.MICROSOFT_CLIENT_ID or ""
        self.client_secret = client_secret or settings.MICROSOFT_CLIENT_SECRET or ""
        self.redirect_uri = redirect_uri or settings.MICROSOFT_REDIRECT_URI
        self.tenant_id = tenant_id or settings.MICROSOFT_TENANT_ID or "common"
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        return "microsoft"

    @property
    def auth_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/authorize"

    @property
    def token_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

    def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "response_mode": "query",
            "scope": " ".join(self.SCOPES),
            "state": state,
        }
        return f"{self.auth_url}?{urllib.parse.urlencode(params)}"

    async def exchange_code(self, code: str) -> Dict[str, Any]:
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.SCOPES),
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.token_url, data=payload)
            if resp.status_code in (400, 401):
                raise CalendarAuthError(
                    f"Microsoft token exchange failed: {resp.text}",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                )
            elif resp.status_code != 200:
                raise CalendarProviderError(
                    f"Microsoft token exchange error ({resp.status_code}): {resp.text}",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                    retryable=resp.status_code >= 500,
                )

            data = resp.json()
            access_token = data.get("access_token")
            refresh_token = data.get("refresh_token")
            expires_in = data.get("expires_in", 3600)
            token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            # Retrieve user profile
            account_identifier: Optional[str] = None
            try:
                me_resp = await client.get(
                    f"{self.GRAPH_BASE_URL}/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if me_resp.status_code == 200:
                    me_data = me_resp.json()
                    account_identifier = me_data.get("mail") or me_data.get("userPrincipalName")
            except Exception:
                pass

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_expires_at": token_expires_at,
                "account_identifier": account_identifier or "microsoft_account",
            }

    async def refresh_tokens(self, refresh_token: str) -> Dict[str, Any]:
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "scope": " ".join(self.SCOPES),
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.token_url, data=payload)
            if resp.status_code in (400, 401):
                raise CalendarAuthError(
                    f"Microsoft token refresh failed: {resp.text}",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                )
            elif resp.status_code != 200:
                raise CalendarProviderError(
                    f"Microsoft token refresh error ({resp.status_code}): {resp.text}",
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
        url = f"{self.GRAPH_BASE_URL}/me/calendars"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code in (401, 403):
                raise CalendarAuthError(
                    "Microsoft Graph list calendars unauthorized.",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                )
            elif resp.status_code == 429:
                raise CalendarRateLimitError(
                    "Microsoft Graph rate limit exceeded.",
                    provider=self.provider_name,
                )
            elif resp.status_code != 200:
                raise CalendarProviderError(
                    f"Microsoft Graph list calendars error ({resp.status_code})",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                    retryable=resp.status_code >= 500,
                )

            items = resp.json().get("value", [])
            calendars = []
            for item in items:
                calendars.append({
                    "id": item.get("id"),
                    "name": item.get("name", "Calendar"),
                    "primary": bool(item.get("isDefaultCalendar", False)),
                    "description": None,
                })
            return calendars

    async def create_event(
        self,
        access_token: str,
        calendar_id: str,
        event_data: Dict[str, Any],
    ) -> str:
        if calendar_id and calendar_id != "primary":
            url = f"{self.GRAPH_BASE_URL}/me/calendars/{calendar_id}/events"
        else:
            url = f"{self.GRAPH_BASE_URL}/me/events"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Microsoft Graph expects ISO-8601 string without offset in dateTime field when timeZone is specified
        start_str = event_data.get("start_time", "")
        end_str = event_data.get("end_time", "")
        timezone_name = event_data.get("timezone", "Asia/Karachi")

        payload = {
            "subject": event_data.get("summary", "Appointment"),
            "body": {
                "contentType": "text",
                "content": event_data.get("description", ""),
            },
            "start": {
                "dateTime": start_str,
                "timeZone": timezone_name,
            },
            "end": {
                "dateTime": end_str,
                "timeZone": timezone_name,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code in (401, 403):
                raise CalendarAuthError(
                    "Microsoft Graph create event unauthorized.",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                )
            elif resp.status_code == 429:
                raise CalendarRateLimitError(
                    "Microsoft Graph rate limit exceeded during event creation.",
                    provider=self.provider_name,
                )
            elif resp.status_code not in (200, 201):
                raise CalendarProviderError(
                    f"Microsoft Graph create event error ({resp.status_code}): {resp.text}",
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
        url = f"{self.GRAPH_BASE_URL}/me/events/{event_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "subject": event_data.get("summary", "Appointment"),
            "body": {
                "contentType": "text",
                "content": event_data.get("description", ""),
            },
            "start": {
                "dateTime": event_data.get("start_time", ""),
                "timeZone": event_data.get("timezone", "Asia/Karachi"),
            },
            "end": {
                "dateTime": event_data.get("end_time", ""),
                "timeZone": event_data.get("timezone", "Asia/Karachi"),
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.patch(url, headers=headers, json=payload)
            if resp.status_code in (401, 403):
                raise CalendarAuthError(
                    "Microsoft Graph update event unauthorized.",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                )
            elif resp.status_code == 429:
                raise CalendarRateLimitError(
                    "Microsoft Graph rate limit exceeded during event update.",
                    provider=self.provider_name,
                )
            elif resp.status_code not in (200, 204):
                raise CalendarProviderError(
                    f"Microsoft Graph update event error ({resp.status_code}): {resp.text}",
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
        url = f"{self.GRAPH_BASE_URL}/me/events/{event_id}"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.delete(url, headers=headers)
            if resp.status_code in (401, 403):
                raise CalendarAuthError(
                    "Microsoft Graph delete event unauthorized.",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                )
            elif resp.status_code == 429:
                raise CalendarRateLimitError(
                    "Microsoft Graph rate limit exceeded during event deletion.",
                    provider=self.provider_name,
                )
            elif resp.status_code not in (200, 204, 404):
                raise CalendarProviderError(
                    f"Microsoft Graph delete event error ({resp.status_code}): {resp.text}",
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
        url = f"{self.GRAPH_BASE_URL}/me/events/{event_id}"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 404:
                return None
            elif resp.status_code in (401, 403):
                raise CalendarAuthError(
                    "Microsoft Graph get event unauthorized.",
                    provider=self.provider_name,
                    status_code=resp.status_code,
                )
            elif resp.status_code != 200:
                raise CalendarProviderError(
                    f"Microsoft Graph get event error ({resp.status_code})",
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


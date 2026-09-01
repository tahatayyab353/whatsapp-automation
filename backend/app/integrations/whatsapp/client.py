from typing import Any, Dict, Optional
import httpx

from app.core.config import settings
from app.integrations.whatsapp.exceptions import (
    WhatsAppAPIError,
    WhatsAppAuthenticationError,
    WhatsAppIntegrationError,
    WhatsAppNetworkError,
    WhatsAppRateLimitError,
)
from app.schemas.whatsapp_message import WhatsAppSendMessageResponse


class WhatsAppClient:
    """
    Foundation client for Meta WhatsApp Cloud API (Graph API).
    Encapsulates per-clinic credentials and endpoint configuration.
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        api_version: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.access_token = access_token or settings.WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
        self.api_version = api_version or settings.WHATSAPP_API_VERSION
        self.timeout = timeout

    @property
    def base_url(self) -> str:
        return f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}"

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _post(self, endpoint: str, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Internal async HTTP helper with structured error mapping.
        """
        if not self.access_token:
            raise WhatsAppAuthenticationError("Missing WhatsApp access token.")
        if not self.phone_number_id:
            raise WhatsAppIntegrationError("Missing WhatsApp phone number ID.")

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=self.headers, json=json_data)
        except httpx.TimeoutException as exc:
            raise WhatsAppNetworkError("WhatsApp API request timed out") from exc
        except httpx.RequestError as exc:
            raise WhatsAppNetworkError(f"WhatsApp API connection error: {str(exc)}") from exc

        if response.status_code == 401 or response.status_code == 403:
            raise WhatsAppAuthenticationError("Invalid or expired WhatsApp Cloud API access token.")
        elif response.status_code == 429:
            raise WhatsAppRateLimitError("Meta WhatsApp API rate limit reached.")
        elif response.status_code != 200:
            raise WhatsAppAPIError(
                f"WhatsApp API error {response.status_code}: {response.text}",
                status_code=response.status_code,
            )

        return response.json()

    async def send_text_message(
        self,
        recipient_phone: str,
        message: str,
    ) -> WhatsAppSendMessageResponse:
        """
        Sends an outbound text message to a customer via Meta WhatsApp Cloud API.
        """
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_phone.lstrip("+"),
            "type": "text",
            "text": {
                "body": message,
            },
        }
        res_data = await self._post("messages", payload)
        return WhatsAppSendMessageResponse.model_validate(res_data)

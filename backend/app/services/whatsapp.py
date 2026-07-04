from typing import Any, cast

import httpx

from app.core.config import Settings
from app.domain.business import normalized_whatsapp_settings
from app.infrastructure.models import Business


class WhatsAppCloudError(RuntimeError):
    pass


class WhatsAppCloudService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

    def phone_number_id_for(self, business: Business) -> str:
        configured = normalized_whatsapp_settings(business.settings)
        return configured.phone_number_id or self._settings.whatsapp_phone_number_id

    def is_configured_for(self, business: Business) -> bool:
        return bool(self._settings.whatsapp_access_token and self.phone_number_id_for(business))

    async def send_text(
        self,
        *,
        business: Business,
        recipient_phone: str,
        body: str,
    ) -> str:
        phone_number_id = self.phone_number_id_for(business)
        if not self._settings.whatsapp_access_token or not phone_number_id:
            raise WhatsAppCloudError("WhatsApp Cloud API is not configured")

        digits = "".join(character for character in recipient_phone if character.isdigit())
        if not digits:
            raise WhatsAppCloudError("WhatsApp recipient phone number is missing")

        response = await self._http.post(
            f"{self._settings.whatsapp_graph_base_url}/{phone_number_id}/messages",
            headers={
                "Authorization": f"Bearer {self._settings.whatsapp_access_token}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": digits,
                "type": "text",
                "text": {"preview_url": False, "body": body[:4096]},
            },
        )
        if response.is_error:
            raise WhatsAppCloudError(f"WhatsApp send failed ({response.status_code})")
        data = cast(dict[str, Any], response.json())
        messages = data.get("messages")
        if isinstance(messages, list) and messages:
            message = messages[0]
            if isinstance(message, dict) and message.get("id"):
                return str(message["id"])
        return ""

    async def close(self) -> None:
        await self._http.aclose()

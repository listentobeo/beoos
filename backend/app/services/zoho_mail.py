from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.parse import urlencode

import httpx

from app.core.config import Settings


class ZohoMailError(RuntimeError):
    pass


class ZohoMailClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

    @property
    def redirect_uri(self) -> str:
        backend_url = str(self._settings.backend_url).rstrip("/")
        return f"{backend_url}/api/v1/integrations/zoho/callback"

    def authorization_url(self, *, state: str) -> str:
        params = {
            "scope": "ZohoMail.accounts.READ,ZohoMail.messages.ALL,ZohoMail.folders.READ",
            "client_id": self._settings.zoho_client_id,
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "redirect_uri": self.redirect_uri,
            "state": state,
        }
        return f"{self._settings.zoho_accounts_base_url}/oauth/v2/auth?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        response = await self._http.post(
            f"{self._settings.zoho_accounts_base_url}/oauth/v2/token",
            data={
                "grant_type": "authorization_code",
                "client_id": self._settings.zoho_client_id,
                "client_secret": self._settings.zoho_client_secret,
                "redirect_uri": self.redirect_uri,
                "code": code,
            },
        )
        if response.is_error:
            raise ZohoMailError(f"Zoho token exchange failed ({response.status_code})")
        return cast(dict[str, Any], response.json())

    async def refresh_access_token(self, refresh_token: str) -> tuple[str, datetime]:
        response = await self._http.post(
            f"{self._settings.zoho_accounts_base_url}/oauth/v2/token",
            data={
                "grant_type": "refresh_token",
                "client_id": self._settings.zoho_client_id,
                "client_secret": self._settings.zoho_client_secret,
                "refresh_token": refresh_token,
            },
        )
        if response.is_error:
            raise ZohoMailError(f"Zoho token refresh failed ({response.status_code})")
        data = response.json()
        expires_at = datetime.now(UTC) + timedelta(seconds=int(data.get("expires_in", 3600)) - 60)
        return str(data["access_token"]), expires_at

    async def get_accounts(self, access_token: str) -> list[dict[str, Any]]:
        data = await self._request("GET", "/api/accounts", access_token)
        return list(data.get("data", []))

    async def get_folders(self, access_token: str, account_id: str) -> list[dict[str, Any]]:
        data = await self._request("GET", f"/api/accounts/{account_id}/folders", access_token)
        return list(data.get("data", []))

    async def list_messages(
        self,
        *,
        access_token: str,
        account_id: str,
        folder_id: str,
        start: int = 1,
        limit: int = 100,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str | int] = {
            "folderId": folder_id,
            "start": start,
            "limit": limit,
        }
        if status:
            params["status"] = status
        data = await self._request(
            "GET",
            f"/api/accounts/{account_id}/messages/view",
            access_token,
            params=params,
        )
        return list(data.get("data", []))

    async def get_message_content(
        self,
        *,
        access_token: str,
        account_id: str,
        folder_id: str,
        message_id: str,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/api/accounts/{account_id}/folders/{folder_id}/messages/{message_id}/content",
            access_token,
        )

    async def reply(
        self,
        *,
        access_token: str,
        account_id: str,
        message_id: str,
        body: str,
    ) -> str:
        data = await self._request(
            "POST",
            f"/api/accounts/{account_id}/messages/{message_id}",
            access_token,
            json={"content": body, "mailFormat": "plaintext", "action": "reply"},
        )
        return str(data.get("data", {}).get("messageId", ""))

    async def mark_read(
        self,
        *,
        access_token: str,
        account_id: str,
        message_id: str,
    ) -> None:
        await self._request(
            "PUT",
            f"/api/accounts/{account_id}/updatemessage",
            access_token,
            json={"mode": "markAsRead", "messageId": [message_id]},
        )

    async def _request(
        self,
        method: str,
        path: str,
        access_token: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        response = await self._http.request(
            method,
            f"{self._settings.zoho_mail_base_url}{path}",
            headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
            **kwargs,
        )
        if response.is_error:
            raise ZohoMailError(f"Zoho Mail request failed ({response.status_code})")
        return cast(dict[str, Any], response.json())

    async def close(self) -> None:
        await self._http.aclose()

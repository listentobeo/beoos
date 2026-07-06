import base64
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage as MIMEEmailMessage
from typing import Any, cast
from urllib.parse import urlencode

import httpx

from app.core.config import Settings


class GmailError(RuntimeError):
    pass


class GmailClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

    @property
    def redirect_uri(self) -> str:
        backend_url = str(self._settings.backend_url).rstrip("/")
        return f"{backend_url}/api/v1/integrations/google/callback"

    def authorization_url(self, *, state: str) -> str:
        params = {
            "client_id": self._settings.google_client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "scope": " ".join(
                [
                    "openid",
                    "email",
                    "https://www.googleapis.com/auth/gmail.readonly",
                    "https://www.googleapis.com/auth/gmail.send",
                ]
            ),
            "state": state,
        }
        return f"{self._settings.google_accounts_base_url}/o/oauth2/v2/auth?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        response = await self._http.post(
            self._settings.google_token_url,
            data={
                "grant_type": "authorization_code",
                "client_id": self._settings.google_client_id,
                "client_secret": self._settings.google_client_secret,
                "redirect_uri": self.redirect_uri,
                "code": code,
            },
        )
        if response.is_error:
            raise GmailError(f"Google token exchange failed ({response.status_code})")
        return cast(dict[str, Any], response.json())

    async def refresh_access_token(self, refresh_token: str) -> tuple[str, datetime]:
        response = await self._http.post(
            self._settings.google_token_url,
            data={
                "grant_type": "refresh_token",
                "client_id": self._settings.google_client_id,
                "client_secret": self._settings.google_client_secret,
                "refresh_token": refresh_token,
            },
        )
        if response.is_error:
            raise GmailError(f"Google token refresh failed ({response.status_code})")
        data = response.json()
        expires_at = datetime.now(UTC) + timedelta(seconds=int(data.get("expires_in", 3600)) - 60)
        return str(data["access_token"]), expires_at

    async def userinfo(self, access_token: str) -> dict[str, Any]:
        response = await self._http.get(
            self._settings.google_userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.is_error:
            raise GmailError(f"Google userinfo request failed ({response.status_code})")
        return cast(dict[str, Any], response.json())

    async def list_messages(
        self,
        *,
        access_token: str,
        label_id: str,
        page_token: str | None = None,
        max_results: int = 100,
        after: datetime | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str | int] = {
            "labelIds": label_id,
            "maxResults": max_results,
        }
        if page_token:
            params["pageToken"] = page_token
        if after:
            params["q"] = f"after:{after.strftime('%Y/%m/%d')}"
        return await self._request(
            "GET",
            "/gmail/v1/users/me/messages",
            access_token,
            params=params,
        )

    async def get_message(self, *, access_token: str, message_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/gmail/v1/users/me/messages/{message_id}",
            access_token,
            params={"format": "full"},
        )

    async def reply(
        self,
        *,
        access_token: str,
        message_id: str,
        to: str,
        subject: str,
        body: str,
    ) -> str:
        original = await self.get_message(access_token=access_token, message_id=message_id)
        thread_id = str(original.get("threadId") or "")
        headers = headers_from_message(original)
        original_message_id = headers.get("message-id")
        message = MIMEEmailMessage()
        message["To"] = to
        message["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        if original_message_id:
            message["In-Reply-To"] = original_message_id
            message["References"] = original_message_id
        message.set_content(body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")
        data = await self._request(
            "POST",
            "/gmail/v1/users/me/messages/send",
            access_token,
            json={"raw": raw, "threadId": thread_id} if thread_id else {"raw": raw},
        )
        return str(data.get("id") or "")

    async def _request(
        self,
        method: str,
        path: str,
        access_token: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        response = await self._http.request(
            method,
            f"{self._settings.google_gmail_base_url}{path}",
            headers={"Authorization": f"Bearer {access_token}"},
            **kwargs,
        )
        if response.is_error:
            raise GmailError(f"Gmail request failed ({response.status_code})")
        return cast(dict[str, Any], response.json())

    async def close(self) -> None:
        await self._http.aclose()


def headers_from_message(message: dict[str, Any]) -> dict[str, str]:
    payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
    values: dict[str, str] = {}
    for item in payload.get("headers") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").lower()
        value = str(item.get("value") or "")
        if name:
            values[name] = value
    return values


def normalize_gmail_message(message: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    headers = headers_from_message(message)
    text_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[dict[str, str]] = []
    _collect_parts(message.get("payload"), text_parts, html_parts, attachments)
    summary = {
        "messageId": message.get("id"),
        "threadId": f"gmail:{message.get('threadId') or message.get('id')}",
        "receivedTime": message.get("internalDate"),
        "sentDateInGMT": message.get("internalDate"),
        "fromAddress": headers.get("from", ""),
        "toAddress": headers.get("to", ""),
        "sender": headers.get("from", ""),
        "receiver": headers.get("to", ""),
        "subject": headers.get("subject", "(no subject)"),
        "attachments": attachments,
    }
    content = {
        "data": {
            "plainText": "\n\n".join(part for part in text_parts if part).strip(),
            "htmlContent": "\n\n".join(part for part in html_parts if part).strip(),
            "attachments": attachments,
        }
    }
    return summary, content


def _collect_parts(
    payload: object,
    text_parts: list[str],
    html_parts: list[str],
    attachments: list[dict[str, str]],
) -> None:
    if not isinstance(payload, dict):
        return
    filename = str(payload.get("filename") or "")
    body = payload.get("body") if isinstance(payload.get("body"), dict) else {}
    data = body.get("data")
    mime_type = str(payload.get("mimeType") or "")
    if filename:
        attachments.append(
            {
                "filename": filename,
                "mime_type": mime_type,
                "attachment_id": str(body.get("attachmentId") or ""),
            }
        )
    elif isinstance(data, str) and mime_type in {"text/plain", "text/html"}:
        decoded = _decode_gmail_body(data)
        if mime_type == "text/plain":
            text_parts.append(decoded)
        else:
            html_parts.append(decoded)
    for part in payload.get("parts") or []:
        _collect_parts(part, text_parts, html_parts, attachments)


def _decode_gmail_body(value: str) -> str:
    padded = value + ("=" * ((4 - len(value) % 4) % 4))
    try:
        return base64.urlsafe_b64decode(padded.encode()).decode("utf-8", errors="replace")
    except Exception:
        return ""

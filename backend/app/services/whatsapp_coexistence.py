from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.infrastructure.models import (
    AuditLog,
    Business,
    DurableJob,
    WhatsAppConnection,
    WhatsAppConnectionStatus,
)
from app.services.crypto import SecretCipher

SyncType = Literal["smb_app_state_sync", "history"]


@dataclass(frozen=True)
class CoexistenceVerification:
    is_on_biz_app: bool
    platform_type: str


class MetaCoexistenceService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.whatsapp_graph_base_url.rstrip("/")

    async def subscribe_waba(self, access_token: str, waba_id: str) -> None:
        await self._request(
            "POST",
            f"/{waba_id}/subscribed_apps",
            access_token=access_token,
        )

    async def verify_phone(
        self,
        access_token: str,
        phone_number_id: str,
    ) -> CoexistenceVerification:
        payload = await self._request(
            "GET",
            f"/{phone_number_id}",
            access_token=access_token,
            params={"fields": "is_on_biz_app,platform_type"},
        )
        return CoexistenceVerification(
            is_on_biz_app=payload.get("is_on_biz_app") is True,
            platform_type=str(payload.get("platform_type") or ""),
        )

    async def request_sync(
        self,
        access_token: str,
        phone_number_id: str,
        sync_type: SyncType,
    ) -> str:
        payload = await self._request(
            "POST",
            f"/{phone_number_id}/smb_app_data",
            access_token=access_token,
            json={"messaging_product": "whatsapp", "sync_type": sync_type},
        )
        request_id = str(payload.get("request_id") or "")
        if not request_id:
            raise ValueError(f"Meta accepted no request ID for {sync_type}")
        return request_id

    async def _request(
        self,
        method: str,
        path: str,
        *,
        access_token: str,
        params: dict[str, str] | None = None,
        json: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            response = await client.request(
                method,
                f"{self._base_url}{path}",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
                json=json,
            )
        if response.is_error:
            raise ValueError(
                f"Meta coexistence request failed ({response.status_code}): "
                f"{_meta_error(response)[:300]}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Meta coexistence API returned a non-object response")
        return payload


async def execute_coexistence_sync_job(
    session: AsyncSession,
    settings: Settings,
    job: DurableJob,
    *,
    sync_type: SyncType,
) -> None:
    connection = await session.scalar(
        select(WhatsAppConnection).where(
            WhatsAppConnection.id == _uuid(job.payload.get("connection_id")),
            WhatsAppConnection.business_id == job.business_id,
        )
    )
    if connection is None:
        raise ValueError("WhatsApp synchronization references a missing connection")
    if connection.connection_mode.value != "coexistence":
        raise ValueError("WhatsApp synchronization requires a coexistence connection")
    if connection.sync_deadline_at and connection.sync_deadline_at < datetime.now(UTC):
        connection.connection_status = WhatsAppConnectionStatus.action_required
        connection.last_error_code = "coexistence_sync_window_expired"
        connection.last_error_message = (
            "The 24-hour synchronization window expired. Offboard and complete signup again."
        )
        await _update_business_sync_settings(session, connection)
        raise ValueError("WhatsApp coexistence synchronization window expired")

    access_token = SecretCipher(settings.secret_encryption_key).decrypt(
        connection.access_token_encrypted
    )
    request_id = await MetaCoexistenceService(settings).request_sync(
        access_token,
        connection.phone_number_id,
        sync_type,
    )
    if sync_type == "smb_app_state_sync":
        connection.contacts_sync_status = "requested"
        connection.contacts_sync_request_id = request_id
    else:
        connection.history_sync_status = "requested"
        connection.history_sync_request_id = request_id
    metadata = dict(connection.connection_metadata or {})
    sync_requests = dict(metadata.get("sync_requests") or {})
    sync_requests[sync_type] = {
        "request_id": request_id,
        "requested_at": datetime.now(UTC).isoformat(),
    }
    metadata["sync_requests"] = sync_requests
    connection.connection_metadata = metadata
    await _update_business_sync_settings(session, connection)
    session.add(
        AuditLog(
            business_id=connection.business_id,
            actor_id="system:whatsapp_sync",
            action=f"whatsapp.coexistence.{sync_type}.requested",
            resource_type="whatsapp_connection",
            resource_id=str(connection.id),
            details={"request_id": request_id},
        )
    )


async def update_business_whatsapp_from_connection(
    session: AsyncSession,
    connection: WhatsAppConnection,
) -> None:
    await _update_business_sync_settings(session, connection)


async def _update_business_sync_settings(
    session: AsyncSession,
    connection: WhatsAppConnection,
) -> None:
    business = await session.get(Business, connection.business_id)
    if business is None:
        raise ValueError("WhatsApp connection business no longer exists")
    settings_blob = dict(business.settings or {})
    raw_whatsapp = settings_blob.get("whatsapp")
    whatsapp = dict(raw_whatsapp) if isinstance(raw_whatsapp, dict) else {}
    whatsapp.update(
        {
            "enabled": connection.connection_status == WhatsAppConnectionStatus.connected,
            "connection_status": connection.connection_status.value,
            "embedded_signup_version": connection.embedded_signup_version,
            "webhook_subscribed_at": _iso(connection.webhook_subscribed_at),
            "coexistence_verified_at": _iso(connection.coexistence_verified_at),
            "sync_deadline_at": _iso(connection.sync_deadline_at),
            "contacts_sync_status": connection.contacts_sync_status,
            "contacts_sync_request_id": connection.contacts_sync_request_id or "",
            "history_sync_status": connection.history_sync_status,
            "history_sync_request_id": connection.history_sync_request_id or "",
            "history_sync_phase": connection.history_sync_phase,
            "history_sync_progress": connection.history_sync_progress,
            "sync_completed_at": _iso(connection.sync_completed_at),
            "last_error_code": connection.last_error_code or "",
            "last_error_message": connection.last_error_message or "",
        }
    )
    settings_blob["whatsapp"] = whatsapp
    business.settings = settings_blob


def _uuid(value: object) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("Durable WhatsApp job contains an invalid connection ID") from exc


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def _meta_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error)
    return str(payload)

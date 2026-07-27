import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.domain.business import normalized_ai_policy, normalized_whatsapp_settings
from app.domain.email import RecommendedAction
from app.infrastructure.database import get_session
from app.infrastructure.models import (
    AuditLog,
    Business,
    Contact,
    Direction,
    DraftStatus,
    EmailAnalysis,
    EmailDraft,
    EmailMessage,
    EmailThread,
    MailboxConnection,
    ThreadStatus,
    WhatsAppConnection,
    WhatsAppConnectionStatus,
    WhatsAppMessageSource,
    WhatsAppWebhookEvent,
)
from app.services.contact_identity import normalize_phone_identity
from app.services.durable_jobs import WHATSAPP_AI_JOB, WHATSAPP_WEBHOOK_JOB, enqueue_job
from app.services.inbox_hygiene import should_skip_ai_draft
from app.services.openai_email import OpenAIEmailService
from app.services.policy import EmailPolicyEngine
from app.services.push_notifications import PushNotificationService
from app.services.whatsapp_coexistence import update_business_whatsapp_from_connection

router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])
logger = structlog.get_logger()


@router.get("")
async def verify_whatsapp_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
    settings: Settings = Depends(get_settings),
) -> Response:
    if mode == "subscribe" and verify_token and verify_token == settings.whatsapp_verify_token:
        return Response(content=challenge or "", media_type="text/plain")
    raise HTTPException(status_code=403, detail="Invalid WhatsApp webhook verification token")


@router.post("")
async def receive_whatsapp_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, str | int]:
    body = await request.body()
    _verify_signature(body, x_hub_signature_256, settings)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid WhatsApp webhook JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid WhatsApp webhook payload")

    accepted = 0
    duplicates = 0
    ignored = 0
    body_hash = hashlib.sha256(body).hexdigest()
    for index, envelope in enumerate(_webhook_envelopes(payload)):
        connection = await _connection_for_envelope(session, envelope)
        if connection is None:
            ignored += 1
            logger.warning(
                "whatsapp_webhook_business_missing",
                phone_number_id=envelope["phone_number_id"],
                waba_id=envelope["waba_id"],
                event_type=envelope["event_type"],
            )
            continue
        event_key = f"{body_hash}:{index}"
        existing = await session.scalar(
            select(WhatsAppWebhookEvent.id).where(WhatsAppWebhookEvent.event_key == event_key)
        )
        if existing is not None:
            duplicates += 1
            continue
        event = WhatsAppWebhookEvent(
            business_id=connection.business_id,
            event_key=event_key,
            event_type=envelope["event_type"],
            waba_id=envelope["waba_id"] or None,
            phone_number_id=envelope["phone_number_id"] or None,
            message_id=envelope["message_id"] or None,
            message_source=envelope["message_source"],
            payload_hash=body_hash,
            status="queued",
            phase=envelope["phase"],
            chunk_order=envelope["chunk_order"],
            progress=envelope["progress"],
            raw_event=envelope["raw_event"],
        )
        session.add(event)
        await session.flush()
        await enqueue_job(
            session,
            business_id=connection.business_id,
            job_type=WHATSAPP_WEBHOOK_JOB,
            payload={"event_id": str(event.id)},
            idempotency_key=f"whatsapp-webhook:{event.id}",
            priority=10,
            max_attempts=8,
        )
        connection.last_webhook_at = datetime.now(UTC)
        accepted += 1

    await session.commit()
    logger.info(
        "whatsapp_webhook_accepted",
        accepted=accepted,
        duplicates=duplicates,
        ignored=ignored,
    )
    return {
        "status": "accepted",
        "accepted": accepted,
        "duplicates": duplicates,
        "ignored": ignored,
    }


class WhatsAppInboundMessage:
    def __init__(
        self,
        *,
        phone_number_id: str,
        display_phone_number: str,
        message_id: str,
        from_phone: str,
        customer_phone: str,
        sender_name: str | None,
        body_text: str,
        media_metadata: list[dict[str, Any]],
        sent_at: datetime,
        raw: dict[str, Any],
        direction: Direction = Direction.inbound,
        enqueue_ai: bool = True,
        is_history: bool = False,
        message_source: WhatsAppMessageSource = WhatsAppMessageSource.customer,
    ) -> None:
        self.phone_number_id = phone_number_id
        self.display_phone_number = display_phone_number
        self.message_id = message_id
        self.from_phone = from_phone
        self.customer_phone = customer_phone
        self.sender_name = sender_name
        self.body_text = body_text
        self.media_metadata = media_metadata
        self.sent_at = sent_at
        self.raw = raw
        self.direction = direction
        self.enqueue_ai = enqueue_ai
        self.is_history = is_history
        self.message_source = message_source


def _verify_signature(body: bytes, signature: str | None, settings: Settings) -> None:
    if not settings.meta_app_secret:
        if settings.app_env in {"staging", "production"}:
            raise HTTPException(status_code=503, detail="Meta webhook signing is not configured")
        return
    if not signature or not signature.startswith("sha256="):
        raise HTTPException(status_code=403, detail="Missing WhatsApp webhook signature")
    expected = hmac.new(settings.meta_app_secret.encode(), body, hashlib.sha256).hexdigest()
    received = signature.removeprefix("sha256=")
    if not hmac.compare_digest(expected, received):
        raise HTTPException(status_code=403, detail="Invalid WhatsApp webhook signature")


def _webhook_envelopes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    envelopes: list[dict[str, Any]] = []
    for entry in _as_list(payload.get("entry")):
        if not isinstance(entry, dict):
            continue
        waba_id = str(entry.get("id") or "")
        for change in _as_list(entry.get("changes")):
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            field = str(change.get("field") or "")
            metadata = value.get("metadata")
            metadata = metadata if isinstance(metadata, dict) else {}
            history_metadata = _history_metadata(value)
            event_type = str(value.get("event") or field or "unknown")
            envelopes.append(
                {
                    "waba_id": waba_id,
                    "phone_number_id": str(metadata.get("phone_number_id") or ""),
                    "event_type": event_type,
                    "message_id": _first_message_id(value),
                    "message_source": _message_source(field),
                    "phase": _optional_int(history_metadata.get("phase")),
                    "chunk_order": _optional_int(history_metadata.get("chunk_order")),
                    "progress": _optional_int(history_metadata.get("progress")),
                    "raw_event": {"entry_id": waba_id, "change": change},
                }
            )
    return envelopes


async def _connection_for_envelope(
    session: AsyncSession,
    envelope: dict[str, Any],
) -> WhatsAppConnection | None:
    phone_number_id = str(envelope.get("phone_number_id") or "")
    waba_id = str(envelope.get("waba_id") or "")
    if phone_number_id:
        connection = await session.scalar(
            select(WhatsAppConnection).where(WhatsAppConnection.phone_number_id == phone_number_id)
        )
        if connection is not None:
            return connection
    if waba_id:
        connection_by_waba: WhatsAppConnection | None = await session.scalar(
            select(WhatsAppConnection).where(WhatsAppConnection.waba_id == waba_id)
        )
        return connection_by_waba
    return None


def _history_metadata(value: dict[str, Any]) -> dict[str, Any]:
    history = _as_list(value.get("history"))
    if history and isinstance(history[0], dict):
        metadata = history[0].get("metadata")
        return metadata if isinstance(metadata, dict) else {}
    return {}


def _first_message_id(value: dict[str, Any]) -> str:
    for key in ("messages", "message_echoes"):
        rows = _as_list(value.get(key))
        if rows and isinstance(rows[0], dict):
            return str(rows[0].get("id") or "")
    return ""


def _message_source(field: str) -> WhatsAppMessageSource:
    if field == "smb_message_echoes":
        return WhatsAppMessageSource.business_app
    if field == "messages":
        return WhatsAppMessageSource.customer
    return WhatsAppMessageSource.unknown


def _optional_int(value: object) -> int | None:
    try:
        return int(str(value)) if value is not None else None
    except ValueError:
        return None


def _iter_inbound_messages(payload: dict[str, Any]) -> list[WhatsAppInboundMessage]:
    messages: list[WhatsAppInboundMessage] = []
    for entry in _as_list(payload.get("entry")):
        for change in _as_list(entry.get("changes")):
            value = change.get("value") if isinstance(change, dict) else None
            if not isinstance(value, dict):
                continue
            metadata = value.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
            phone_number_id = str(metadata.get("phone_number_id") or "")
            display_phone_number = str(metadata.get("display_phone_number") or "")
            contact_names = _contact_names(value)
            for message in _as_list(value.get("messages")):
                if not isinstance(message, dict):
                    continue
                message_id = str(message.get("id") or "")
                from_phone = str(message.get("from") or "")
                if not message_id or not from_phone:
                    continue
                body_text, media_metadata = _message_body_and_media(message)
                messages.append(
                    WhatsAppInboundMessage(
                        phone_number_id=phone_number_id,
                        display_phone_number=display_phone_number,
                        message_id=message_id,
                        from_phone=from_phone,
                        customer_phone=from_phone,
                        sender_name=contact_names.get(from_phone),
                        body_text=body_text,
                        media_metadata=media_metadata,
                        sent_at=_timestamp(message.get("timestamp")),
                        raw=message,
                        direction=Direction.inbound,
                        enqueue_ai=True,
                        is_history=False,
                        message_source=WhatsAppMessageSource.customer,
                    )
                )
    return messages


async def process_whatsapp_webhook_event(
    session: AsyncSession,
    settings: Settings,
    *,
    event_id: UUID,
    business_id: UUID,
) -> None:
    event = await session.scalar(
        select(WhatsAppWebhookEvent).where(
            WhatsAppWebhookEvent.id == event_id,
            WhatsAppWebhookEvent.business_id == business_id,
        )
    )
    if event is None:
        raise ValueError("WhatsApp webhook job references a missing event")
    if event.status in {"processed", "ignored"}:
        return
    raw_event = event.raw_event or {}
    change = raw_event.get("change")
    if not isinstance(change, dict):
        event.status = "ignored"
        event.processed_at = datetime.now(UTC)
        return
    value = change.get("value")
    if not isinstance(value, dict):
        event.status = "ignored"
        event.processed_at = datetime.now(UTC)
        return
    connection = await session.scalar(
        select(WhatsAppConnection).where(
            WhatsAppConnection.business_id == business_id,
            WhatsAppConnection.waba_id == event.waba_id,
        )
    )
    if connection is None and event.phone_number_id:
        connection = await session.scalar(
            select(WhatsAppConnection).where(
                WhatsAppConnection.business_id == business_id,
                WhatsAppConnection.phone_number_id == event.phone_number_id,
            )
        )
    if connection is None:
        event.status = "ignored"
        event.processed_at = datetime.now(UTC)
        return

    event.status = "processing"
    field = str(change.get("field") or "")
    if field == "messages":
        await _process_messages_event(session, settings, connection, value)
    elif field == "history":
        await _process_history_event(session, settings, connection, value)
    elif field == "smb_app_state_sync":
        await _process_state_sync_event(session, connection, value)
    elif field == "smb_message_echoes":
        await _process_echo_event(session, settings, connection, value)
    elif field == "account_update" or value.get("event"):
        await _process_account_update(session, connection, value)
    else:
        event.status = "ignored"
        event.processed_at = datetime.now(UTC)
        return

    event.status = "processed"
    event.processing_error = None
    event.processed_at = datetime.now(UTC)
    await update_business_whatsapp_from_connection(session, connection)


async def _process_messages_event(
    session: AsyncSession,
    settings: Settings,
    connection: WhatsAppConnection,
    value: dict[str, Any],
) -> None:
    for error in _as_list(value.get("errors")):
        if isinstance(error, dict) and str(error.get("code") or "") == "131060":
            connection.last_error_code = "131060"
            connection.last_error_message = (
                "A message is available only in the WhatsApp Business app or an "
                "unsupported companion device."
            )
    business = await session.get(Business, connection.business_id)
    if business is None:
        raise ValueError("WhatsApp webhook business no longer exists")
    for message in _as_list(value.get("messages")):
        if not isinstance(message, dict):
            continue
        if any(
            isinstance(error, dict) and str(error.get("code") or "") == "131060"
            for error in _as_list(message.get("errors"))
        ):
            connection.last_error_code = "131060"
            connection.last_error_message = (
                "Check the WhatsApp Business app for a message from an unsupported "
                "companion device."
            )
            continue
        message_type = str(message.get("type") or "")
        if message_type in {"edit", "revoke"}:
            await _apply_message_mutation(session, business.id, message)
            continue
        item = _message_item(
            value,
            message,
            direction=Direction.inbound,
            customer_phone=str(message.get("from") or ""),
            enqueue_ai=True,
            is_history=False,
            message_source=WhatsAppMessageSource.customer,
        )
        if item is None:
            continue
        thread_id = await _import_whatsapp_message(session, settings, business, item)
        if thread_id is not None:
            await PushNotificationService(settings).send_new_inbox_message(
                session,
                business_id=business.id,
                thread_id=thread_id,
                title=f"New WhatsApp message for {business.name}",
                body=f"{item.sender_name or item.customer_phone}: {item.body_text}",
                channel="whatsapp",
            )


async def _process_echo_event(
    session: AsyncSession,
    settings: Settings,
    connection: WhatsAppConnection,
    value: dict[str, Any],
) -> None:
    business = await session.get(Business, connection.business_id)
    if business is None:
        raise ValueError("WhatsApp echo business no longer exists")
    for message in _as_list(value.get("message_echoes")):
        if not isinstance(message, dict):
            continue
        item = _message_item(
            value,
            message,
            direction=Direction.outbound,
            customer_phone=str(message.get("to") or ""),
            enqueue_ai=False,
            is_history=False,
            message_source=WhatsAppMessageSource.business_app,
        )
        if item is not None:
            await _import_whatsapp_message(session, settings, business, item)


async def _process_history_event(
    session: AsyncSession,
    settings: Settings,
    connection: WhatsAppConnection,
    value: dict[str, Any],
) -> None:
    business = await session.get(Business, connection.business_id)
    if business is None:
        raise ValueError("WhatsApp history business no longer exists")
    metadata_value = value.get("metadata")
    value_metadata = metadata_value if isinstance(metadata_value, dict) else {}
    business_phone = str(
        value_metadata.get("display_phone_number") or connection.display_phone_number or ""
    )
    for history in _as_list(value.get("history")):
        if not isinstance(history, dict):
            continue
        errors = _as_list(history.get("errors"))
        if any(
            isinstance(error, dict) and str(error.get("code") or "") == "2593109"
            for error in errors
        ):
            connection.history_sync_status = "declined"
            connection.last_error_code = "2593109"
            connection.last_error_message = (
                "History sharing was declined in the WhatsApp Business app."
            )
            continue
        history_metadata_value = history.get("metadata")
        history_metadata = (
            history_metadata_value if isinstance(history_metadata_value, dict) else {}
        )
        phase = _optional_int(history_metadata.get("phase"))
        progress = _optional_int(history_metadata.get("progress"))
        if phase is not None:
            connection.history_sync_phase = max(connection.history_sync_phase or 0, phase)
        if progress is not None:
            connection.history_sync_progress = max(connection.history_sync_progress, progress)
        connection.history_sync_status = "receiving"
        for thread in _as_list(history.get("threads")):
            if not isinstance(thread, dict):
                continue
            customer_phone = str(thread.get("id") or "")
            for message in _as_list(thread.get("messages")):
                if not isinstance(message, dict):
                    continue
                from_phone = str(message.get("from") or "")
                direction = (
                    Direction.outbound
                    if _digits(from_phone) == _digits(business_phone)
                    else Direction.inbound
                )
                item = _message_item(
                    value,
                    message,
                    direction=direction,
                    customer_phone=customer_phone,
                    enqueue_ai=False,
                    is_history=True,
                    message_source=(
                        WhatsAppMessageSource.business_app
                        if direction == Direction.outbound
                        else WhatsAppMessageSource.customer
                    ),
                )
                if item is not None:
                    await _import_whatsapp_message(session, settings, business, item)
        if phase == 2 and progress == 100:
            completed_at = datetime.now(UTC)
            connection.history_sync_status = "completed"
            connection.last_history_sync_at = completed_at
            connection.sync_completed_at = completed_at
    for media_message in _as_list(value.get("messages")):
        if isinstance(media_message, dict):
            await _apply_history_media(session, business.id, media_message)


async def _process_state_sync_event(
    session: AsyncSession,
    connection: WhatsAppConnection,
    value: dict[str, Any],
) -> None:
    for row in _as_list(value.get("state_sync")):
        if not isinstance(row, dict) or row.get("type") != "contact":
            continue
        contact_value = row.get("contact")
        contact_data = contact_value if isinstance(contact_value, dict) else {}
        phone = str(contact_data.get("phone_number") or "")
        if not phone:
            continue
        contact = await session.scalar(
            select(Contact).where(
                Contact.business_id == connection.business_id,
                Contact.email == _synthetic_whatsapp_email(phone),
            )
        )
        if str(row.get("action") or "") == "remove":
            if contact is not None:
                await session.delete(contact)
            continue
        name = str(contact_data.get("full_name") or contact_data.get("first_name") or "")
        if contact is None:
            session.add(
                Contact(
                    business_id=connection.business_id,
                    email=_synthetic_whatsapp_email(phone),
                    name=name or None,
                    phone=phone,
                    preferred_channel="whatsapp",
                )
            )
        else:
            contact.name = name or contact.name
            contact.phone = phone
            contact.preferred_channel = "whatsapp"
    connection.contacts_sync_status = "completed"


async def _process_account_update(
    session: AsyncSession,
    connection: WhatsAppConnection,
    value: dict[str, Any],
) -> None:
    event_name = str(value.get("event") or "")
    if event_name in {"PARTNER_REMOVED", "ACCOUNT_OFFBOARDED"}:
        connection.connection_status = WhatsAppConnectionStatus.disconnected
        connection.last_error_code = event_name.lower()
        disconnection = value.get("disconnection_info")
        connection.last_error_message = (
            str(disconnection)[:500]
            if isinstance(disconnection, dict)
            else "The WhatsApp Business app disconnected from Cloud API."
        )
    elif event_name == "ACCOUNT_RECONNECTED":
        connection.connection_status = WhatsAppConnectionStatus.connected
        connection.last_error_code = None
        connection.last_error_message = None
    else:
        return
    session.add(
        AuditLog(
            business_id=connection.business_id,
            actor_id="system:meta_webhook",
            action=f"whatsapp.account.{event_name.lower()}",
            resource_type="whatsapp_connection",
            resource_id=str(connection.id),
            details={"event": event_name, "disconnection_info": value.get("disconnection_info")},
        )
    )


async def _apply_message_mutation(
    session: AsyncSession,
    business_id: UUID,
    event_message: dict[str, Any],
) -> None:
    message_type = str(event_message.get("type") or "")
    mutation = event_message.get(message_type)
    mutation_data = mutation if isinstance(mutation, dict) else {}
    original_id = str(mutation_data.get("original_message_id") or "")
    if not original_id:
        return
    original = await session.scalar(
        select(EmailMessage)
        .join(EmailThread, EmailThread.id == EmailMessage.thread_id)
        .where(
            EmailThread.business_id == business_id,
            EmailMessage.provider_message_id == original_id,
        )
    )
    if original is None:
        return
    metadata = list(original.attachment_metadata or [])
    metadata.append({"source": "whatsapp", "mutation": event_message})
    original.attachment_metadata = metadata
    if message_type == "revoke":
        original.body_text = "[WhatsApp message revoked]"
        return
    edited_message = mutation_data.get("message")
    edited = edited_message if isinstance(edited_message, dict) else {}
    body_text, media_metadata = _message_body_and_media(edited)
    original.body_text = body_text
    if media_metadata:
        original.attachment_metadata = [*metadata, *media_metadata]


async def _apply_history_media(
    session: AsyncSession,
    business_id: UUID,
    media_message: dict[str, Any],
) -> None:
    message_id = str(media_message.get("id") or "")
    if not message_id:
        return
    original = await session.scalar(
        select(EmailMessage)
        .join(EmailThread, EmailThread.id == EmailMessage.thread_id)
        .where(
            EmailThread.business_id == business_id,
            EmailMessage.provider_message_id == message_id,
        )
    )
    if original is None:
        return
    body_text, media_metadata = _message_body_and_media(media_message)
    original.body_text = body_text
    if media_metadata:
        original.attachment_metadata = [
            *(original.attachment_metadata or []),
            *media_metadata,
        ]


def _message_item(
    value: dict[str, Any],
    message: dict[str, Any],
    *,
    direction: Direction,
    customer_phone: str,
    enqueue_ai: bool,
    is_history: bool,
    message_source: WhatsAppMessageSource,
) -> WhatsAppInboundMessage | None:
    metadata_value = value.get("metadata")
    metadata = metadata_value if isinstance(metadata_value, dict) else {}
    message_id = str(message.get("id") or "")
    from_phone = str(message.get("from") or "")
    if not message_id or not customer_phone:
        return None
    body_text, media_metadata = _message_body_and_media(message)
    names = _contact_names(value)
    return WhatsAppInboundMessage(
        phone_number_id=str(metadata.get("phone_number_id") or ""),
        display_phone_number=str(metadata.get("display_phone_number") or ""),
        message_id=message_id,
        from_phone=from_phone,
        customer_phone=customer_phone,
        sender_name=names.get(customer_phone),
        body_text=body_text,
        media_metadata=media_metadata,
        sent_at=_timestamp(message.get("timestamp")),
        raw=message,
        direction=direction,
        enqueue_ai=enqueue_ai,
        is_history=is_history,
        message_source=message_source,
    )


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _contact_names(value: dict[str, Any]) -> dict[str, str]:
    names: dict[str, str] = {}
    for contact in _as_list(value.get("contacts")):
        if not isinstance(contact, dict):
            continue
        wa_id = str(contact.get("wa_id") or "")
        profile_value = contact.get("profile")
        profile = profile_value if isinstance(profile_value, dict) else {}
        name = str(profile.get("name") or "")
        if wa_id and name:
            names[wa_id] = name
    return names


def _message_body_and_media(message: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    text_value = message.get("text")
    text = text_value if isinstance(text_value, dict) else {}
    if text.get("body"):
        return str(text["body"]), []

    message_type = str(message.get("type") or "message")
    media_value = message.get(message_type)
    media = media_value if isinstance(media_value, dict) else {}
    media_id = str(media.get("id") or "")
    caption = str(media.get("caption") or "").strip()
    filename = str(media.get("filename") or "").strip()
    mime_type = str(media.get("mime_type") or "").strip()
    sha256 = str(media.get("sha256") or "").strip()
    if media_id:
        label = filename or caption or media_id
        body = caption or f"[WhatsApp {message_type} received: {label}]"
        return body, [
            {
                "source": "whatsapp",
                "media_type": message_type,
                "media_id": media_id,
                "caption": caption,
                "filename": filename,
                "mime_type": mime_type,
                "sha256": sha256,
            }
        ]
    return _non_text_placeholder(message), []


def _non_text_placeholder(message: dict[str, Any]) -> str:
    message_type = str(message.get("type") or "message")
    return f"[WhatsApp {message_type} received. Open Meta/WhatsApp media support to inspect it.]"


def _timestamp(value: object) -> datetime:
    text = str(value or "")
    if text.isdigit():
        return datetime.fromtimestamp(int(text), tz=UTC)
    return datetime.now(UTC)


async def _find_business_for_phone_number(
    session: AsyncSession,
    phone_number_id: str,
    display_phone_number: str,
) -> Business | None:
    if phone_number_id:
        connection = await session.scalar(
            select(WhatsAppConnection).where(
                WhatsAppConnection.phone_number_id == phone_number_id,
                WhatsAppConnection.connection_status == WhatsAppConnectionStatus.connected,
            )
        )
        if connection:
            connection.last_webhook_at = datetime.now(UTC)
            return await session.get(Business, connection.business_id)

    businesses = (await session.scalars(select(Business))).all()
    display_digits = _digits(display_phone_number)
    for business in businesses:
        whatsapp = normalized_whatsapp_settings(business.settings)
        if not whatsapp.enabled:
            continue
        if whatsapp.phone_number_id and whatsapp.phone_number_id == phone_number_id:
            return business
        if (
            whatsapp.display_phone_number
            and _digits(whatsapp.display_phone_number) == display_digits
        ):
            return business
        if display_digits and _digits(business.whatsapp_number) == display_digits:
            return business
    return None


async def _import_whatsapp_message(
    session: AsyncSession,
    settings: Settings,
    business: Business,
    item: WhatsAppInboundMessage,
) -> UUID | None:
    mailbox = await _get_or_create_whatsapp_mailbox(session, business.id, item)
    exists = await session.scalar(
        select(EmailMessage.id).where(
            EmailMessage.mailbox_id == mailbox.id,
            EmailMessage.provider_message_id == item.message_id,
        )
    )
    if exists:
        return None

    contact = await _get_or_create_whatsapp_contact(session, business.id, item)
    provider_thread_id = (
        f"whatsapp:{item.phone_number_id or _digits(business.whatsapp_number)}:"
        f"{item.customer_phone}"
    )
    thread = await session.scalar(
        select(EmailThread).where(
            EmailThread.business_id == business.id,
            EmailThread.provider_thread_id == provider_thread_id,
        )
    )
    subject = f"WhatsApp conversation with {item.sender_name or item.customer_phone}"
    unread_increment = 1 if item.direction == Direction.inbound and not item.is_history else 0
    if thread is None:
        thread = EmailThread(
            business_id=business.id,
            contact_id=contact.id,
            provider_thread_id=provider_thread_id,
            subject=subject,
            latest_message_at=item.sent_at,
            unread_count=unread_increment,
        )
        session.add(thread)
        await session.flush()
    else:
        thread.latest_message_at = max(thread.latest_message_at, item.sent_at)
        thread.unread_count += unread_increment

    message = EmailMessage(
        thread_id=thread.id,
        mailbox_id=mailbox.id,
        provider_message_id=item.message_id,
        direction=item.direction,
        sender_email=(
            _synthetic_whatsapp_email(item.customer_phone)
            if item.direction == Direction.inbound
            else business.primary_email
        ),
        sender_name=item.sender_name,
        recipients=(
            [business.whatsapp_number]
            if item.direction == Direction.inbound
            else [item.customer_phone]
        ),
        subject=subject,
        body_text=item.body_text,
        body_html=None,
        attachment_metadata=[
            *item.media_metadata,
            {
                "source": "whatsapp",
                "phone_number_id": item.phone_number_id,
                "display_phone_number": item.display_phone_number,
                "from_phone": item.from_phone,
                "customer_phone": item.customer_phone,
                "message_source": item.message_source.value,
                "is_history": item.is_history,
                "raw": item.raw,
            },
        ],
        sent_at=item.sent_at,
    )
    session.add(message)
    await session.flush()
    if item.enqueue_ai and item.direction == Direction.inbound:
        await enqueue_job(
            session,
            business_id=business.id,
            job_type=WHATSAPP_AI_JOB,
            payload={
                "contact_id": str(contact.id),
                "thread_id": str(thread.id),
                "message_id": str(message.id),
            },
            idempotency_key=f"whatsapp-ai:{message.id}",
        )
    return thread.id


async def _get_or_create_whatsapp_mailbox(
    session: AsyncSession,
    business_id: UUID,
    item: WhatsAppInboundMessage,
) -> MailboxConnection:
    identifier = item.phone_number_id or item.display_phone_number or "unconfigured"
    mailbox_email = f"whatsapp+{identifier}@beoos.local".lower()
    mailbox = await session.scalar(
        select(MailboxConnection).where(
            MailboxConnection.business_id == business_id,
            MailboxConnection.provider == "whatsapp",
            MailboxConnection.email_address == mailbox_email,
        )
    )
    if mailbox is None:
        mailbox = MailboxConnection(
            business_id=business_id,
            provider="whatsapp",
            email_address=mailbox_email,
            provider_account_id=item.phone_number_id or None,
            history_start_at=datetime.now(UTC) - timedelta(days=365),
            active=True,
        )
        session.add(mailbox)
        await session.flush()
    return mailbox


async def _get_or_create_whatsapp_contact(
    session: AsyncSession,
    business_id: UUID,
    item: WhatsAppInboundMessage,
) -> Contact:
    contact_email = _synthetic_whatsapp_email(item.customer_phone)
    contact = await session.scalar(
        select(Contact).where(Contact.business_id == business_id, Contact.email == contact_email)
    )
    if contact is None:
        contact = Contact(
            business_id=business_id,
            email=contact_email,
            name=item.sender_name,
            phone=item.customer_phone,
            preferred_channel="whatsapp",
        )
        session.add(contact)
        await session.flush()
    else:
        if item.sender_name and not contact.name:
            contact.name = item.sender_name
        if item.customer_phone and not contact.phone:
            contact.phone = item.customer_phone
        contact.preferred_channel = "whatsapp"
    return contact


async def _run_whatsapp_ai_intake(
    session: AsyncSession,
    settings: Settings,
    business: Business,
    contact: Contact,
    thread: EmailThread,
    message: EmailMessage,
) -> None:
    if not settings.ai_configured:
        thread.status = ThreadStatus.needs_approval
        message.processed_at = datetime.now(UTC)
        provider_name = "Replicate" if settings.effective_ai_provider == "replicate" else "OpenAI"
        session.add(
            EmailDraft(
                thread_id=thread.id,
                source_message_id=message.id,
                subject=f"Re: {thread.subject}",
                body_text=f"WhatsApp message received. Add a {provider_name} key to draft replies.",
                draft_type="whatsapp_reply",
                status=DraftStatus.pending,
                auto_send_eligible=False,
                policy_reasons=[f"{provider_name} key is not configured"],
            )
        )
        return

    policy = normalized_ai_policy(business.settings)
    context_rows = (
        await session.scalars(
            select(EmailMessage)
            .where(EmailMessage.thread_id == thread.id, EmailMessage.id != message.id)
            .order_by(EmailMessage.sent_at.desc())
            .limit(6)
        )
    ).all()
    recent_context = "\n\n".join(
        f"{row.direction.value}: {row.body_text[:1200]}" for row in reversed(context_rows)
    )
    ai = OpenAIEmailService(settings)
    try:
        triage, response_id = await ai.triage_and_draft(
            subject=thread.subject,
            sender_email=message.sender_email,
            sender_name=message.sender_name,
            body_text=message.body_text,
            is_existing_client=contact.is_existing_client,
            recent_thread_context=recent_context,
            business_name=business.name,
            reply_signature=business.reply_signature,
            whatsapp_link=_whatsapp_link(business.whatsapp_number),
            business_policy_instructions=policy.custom_instructions,
        )
    except Exception as exc:
        logger.exception(
            "whatsapp_ai_intake_failed",
            business_id=str(business.id),
            thread_id=str(thread.id),
            message_id=str(message.id),
            provider=settings.effective_ai_provider,
            model=settings.effective_ai_model,
        )
        thread.status = ThreadStatus.needs_approval
        message.processed_at = datetime.now(UTC)
        session.add(
            EmailDraft(
                thread_id=thread.id,
                source_message_id=message.id,
                subject=f"Re: {thread.subject}",
                body_text="WhatsApp message needs manual review.",
                draft_type="whatsapp_reply",
                status=DraftStatus.pending,
                auto_send_eligible=False,
                policy_reasons=[f"AI intake failed: {exc.__class__.__name__}: {str(exc)[:180]}"],
            )
        )
        return
    finally:
        await ai.close()

    session.add(
        EmailAnalysis(
            message_id=message.id,
            category=triage.category,
            intent=triage.intent,
            confidence=Decimal(str(triage.confidence)),
            urgency=triage.urgency,
            is_deal=triage.is_deal,
            is_professional=triage.is_professional,
            risk_flags=list(triage.risk_flags),
            extracted_fields=triage.extracted_fields.model_dump(),
            recommended_action=triage.recommended_action.value,
            model=settings.effective_ai_model,
            response_id=response_id,
        )
    )
    thread.category = triage.category
    thread.is_deal = triage.is_deal
    thread.is_professional = triage.is_professional
    thread.priority = 100 if triage.urgency else (50 if triage.is_deal else 10)
    if should_skip_ai_draft(triage):
        thread.status = ThreadStatus.closed
        thread.unread_count = 0
        message.processed_at = datetime.now(UTC)
        logger.info(
            "whatsapp_ai_draft_skipped_for_noise",
            business_id=str(business.id),
            thread_id=str(thread.id),
            category=triage.category.value,
            recommended_action=triage.recommended_action.value,
        )
        return
    decision = EmailPolicyEngine(
        signature=business.reply_signature,
        whatsapp_number=business.whatsapp_number,
        policy=policy,
    ).evaluate(
        triage,
        is_existing_client=contact.is_existing_client,
        draft_body=triage.acknowledgement_body,
    )
    draft_type = (
        "whatsapp_reply"
        if triage.recommended_action != RecommendedAction.route_whatsapp
        else "whatsapp_reply"
    )
    session.add(
        EmailDraft(
            thread_id=thread.id,
            source_message_id=message.id,
            subject=triage.acknowledgement_subject,
            body_text=triage.acknowledgement_body,
            draft_type=draft_type,
            status=DraftStatus.pending,
            auto_send_eligible=False,
            policy_reasons=[
                *decision.reasons,
                "WhatsApp replies require approval before sending",
            ],
        )
    )
    thread.status = ThreadStatus.needs_approval
    message.processed_at = datetime.now(UTC)


def _digits(value: str) -> str:
    return normalize_phone_identity(value)


def _synthetic_whatsapp_email(phone: str) -> str:
    digits = _digits(phone) or "unknown"
    return f"whatsapp+{digits}@channels.beoos.app"


def _whatsapp_link(number: str) -> str:
    digits = _digits(number)
    return f"https://wa.me/{digits}"

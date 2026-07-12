import hashlib
import hmac
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
)
from app.services.openai_email import OpenAIEmailService
from app.services.policy import EmailPolicyEngine
from app.services.push_notifications import PushNotificationService

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
) -> dict[str, str]:
    body = await request.body()
    _verify_signature(body, x_hub_signature_256, settings)
    payload = await request.json()
    imported = 0
    duplicates = 0
    ignored = 0

    for item in _iter_inbound_messages(payload):
        business = await _find_business_for_phone_number(
            session,
            item.phone_number_id,
            item.display_phone_number,
        )
        if business is None:
            ignored += 1
            logger.warning(
                "whatsapp_webhook_business_missing",
                phone_number_id=item.phone_number_id,
                display_phone_number=item.display_phone_number,
                from_phone=item.from_phone,
            )
            continue
        created = await _import_whatsapp_message(session, settings, business, item)
        if created:
            imported += 1
            await PushNotificationService(settings).send_new_inbox_message(
                session,
                business_id=business.id,
                thread_id=created,
                title=f"New WhatsApp message for {business.name}",
                body=f"{item.sender_name or item.from_phone}: {item.body_text}",
                channel="whatsapp",
            )
        else:
            duplicates += 1

    await session.commit()
    logger.info(
        "whatsapp_webhook_processed",
        imported=imported,
        duplicates=duplicates,
        ignored=ignored,
    )
    return {"status": "ok"}


class WhatsAppInboundMessage:
    def __init__(
        self,
        *,
        phone_number_id: str,
        display_phone_number: str,
        message_id: str,
        from_phone: str,
        sender_name: str | None,
        body_text: str,
        sent_at: datetime,
        raw: dict[str, Any],
    ) -> None:
        self.phone_number_id = phone_number_id
        self.display_phone_number = display_phone_number
        self.message_id = message_id
        self.from_phone = from_phone
        self.sender_name = sender_name
        self.body_text = body_text
        self.sent_at = sent_at
        self.raw = raw


def _verify_signature(body: bytes, signature: str | None, settings: Settings) -> None:
    if not settings.meta_app_secret:
        return
    if not signature or not signature.startswith("sha256="):
        raise HTTPException(status_code=403, detail="Missing WhatsApp webhook signature")
    expected = hmac.new(settings.meta_app_secret.encode(), body, hashlib.sha256).hexdigest()
    received = signature.removeprefix("sha256=")
    if not hmac.compare_digest(expected, received):
        raise HTTPException(status_code=403, detail="Invalid WhatsApp webhook signature")


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
                text_value = message.get("text")
                text = text_value if isinstance(text_value, dict) else {}
                body_text = str(text.get("body") or _non_text_placeholder(message))
                messages.append(
                    WhatsAppInboundMessage(
                        phone_number_id=phone_number_id,
                        display_phone_number=display_phone_number,
                        message_id=message_id,
                        from_phone=from_phone,
                        sender_name=contact_names.get(from_phone),
                        body_text=body_text,
                        sent_at=_timestamp(message.get("timestamp")),
                        raw=message,
                    )
                )
    return messages


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
    businesses = (await session.scalars(select(Business))).all()
    display_digits = _digits(display_phone_number)
    for business in businesses:
        whatsapp = normalized_whatsapp_settings(business.settings)
        if not whatsapp.enabled:
            continue
        if (
            whatsapp.phone_number_id
            and whatsapp.phone_number_id == phone_number_id
        ):
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
        f"whatsapp:{item.phone_number_id or _digits(business.whatsapp_number)}:{item.from_phone}"
    )
    thread = await session.scalar(
        select(EmailThread).where(
            EmailThread.business_id == business.id,
            EmailThread.provider_thread_id == provider_thread_id,
        )
    )
    subject = f"WhatsApp message from {item.sender_name or item.from_phone}"
    if thread is None:
        thread = EmailThread(
            business_id=business.id,
            contact_id=contact.id,
            provider_thread_id=provider_thread_id,
            subject=subject,
            latest_message_at=item.sent_at,
            unread_count=1,
        )
        session.add(thread)
        await session.flush()
    else:
        thread.latest_message_at = max(thread.latest_message_at, item.sent_at)
        thread.unread_count += 1

    message = EmailMessage(
        thread_id=thread.id,
        mailbox_id=mailbox.id,
        provider_message_id=item.message_id,
        direction=Direction.inbound,
        sender_email=_synthetic_whatsapp_email(item.from_phone),
        sender_name=item.sender_name,
        recipients=[business.whatsapp_number],
        subject=subject,
        body_text=item.body_text,
        body_html=None,
        attachment_metadata=[
            {
                "source": "whatsapp",
                "phone_number_id": item.phone_number_id,
                "display_phone_number": item.display_phone_number,
                "from_phone": item.from_phone,
                "raw": item.raw,
            }
        ],
        sent_at=item.sent_at,
    )
    session.add(message)
    await session.flush()
    await _run_whatsapp_ai_intake(session, settings, business, contact, thread, message)
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
    contact_email = _synthetic_whatsapp_email(item.from_phone)
    contact = await session.scalar(
        select(Contact).where(Contact.business_id == business_id, Contact.email == contact_email)
    )
    if contact is None:
        contact = Contact(
            business_id=business_id,
            email=contact_email,
            name=item.sender_name,
            phone=item.from_phone,
            preferred_channel="whatsapp",
        )
        session.add(contact)
        await session.flush()
    else:
        if item.sender_name and not contact.name:
            contact.name = item.sender_name
        if item.from_phone and not contact.phone:
            contact.phone = item.from_phone
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
    if (
        (settings.ai_provider == "openai" and not settings.openai_api_key)
        or (settings.ai_provider == "replicate" and not settings.replicate_api_token)
    ):
        thread.status = ThreadStatus.needs_approval
        message.processed_at = datetime.now(UTC)
        provider_name = "Replicate" if settings.ai_provider == "replicate" else "OpenAI"
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
                policy_reasons=[f"AI intake failed: {exc.__class__.__name__}"],
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
            model=(
                f"replicate:{settings.replicate_model}"
                if settings.ai_provider == "replicate"
                else settings.openai_model
            ),
            response_id=response_id,
        )
    )
    thread.category = triage.category
    thread.is_deal = triage.is_deal
    thread.is_professional = triage.is_professional
    thread.priority = 100 if triage.urgency else (50 if triage.is_deal else 10)
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
                "WhatsApp replies require approval in Module 1.6",
            ],
        )
    )
    thread.status = ThreadStatus.needs_approval
    message.processed_at = datetime.now(UTC)


def _digits(value: str) -> str:
    return "".join(character for character in str(value) if character.isdigit())


def _synthetic_whatsapp_email(phone: str) -> str:
    digits = _digits(phone) or "unknown"
    return f"whatsapp+{digits}@channels.beoos.app"


def _whatsapp_link(number: str) -> str:
    digits = _digits(number)
    return f"https://wa.me/{digits}"

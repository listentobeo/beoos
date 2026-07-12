from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.domain.business import normalized_ai_policy, website_form_key
from app.domain.email import RecommendedAction
from app.domain.forms import WebsiteLeadResult, WebsiteLeadSubmission
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
from app.services.alerts import AlertService
from app.services.openai_email import OpenAIEmailService
from app.services.policy import EmailPolicyEngine
from app.services.push_notifications import PushNotificationService

router = APIRouter(prefix="/forms", tags=["forms"])
logger = structlog.get_logger()


@router.post("/{business_slug}/lead", response_model=WebsiteLeadResult, status_code=201)
async def submit_website_lead(
    business_slug: str,
    payload: WebsiteLeadSubmission,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> WebsiteLeadResult:
    business = await session.scalar(select(Business).where(Business.slug == business_slug))
    if business is None:
        raise HTTPException(status_code=404, detail="Business form endpoint not found")
    if payload.form_key != website_form_key(business.settings):
        raise HTTPException(status_code=403, detail="Invalid website form key")

    now = datetime.now(UTC)
    mailbox = await _get_or_create_website_form_mailbox(session, business.id, business.slug, now)
    contact = await _get_or_create_contact(session, business.id, payload)
    provider_id = f"website_form:{uuid4()}"
    subject = _subject(payload)
    body_text = _body(payload)
    thread = EmailThread(
        business_id=business.id,
        contact_id=contact.id,
        provider_thread_id=provider_id,
        subject=subject,
        latest_message_at=now,
        unread_count=1,
    )
    session.add(thread)
    await session.flush()
    message = EmailMessage(
        thread_id=thread.id,
        mailbox_id=mailbox.id,
        provider_message_id=provider_id,
        direction=Direction.inbound,
        sender_email=str(payload.email).lower(),
        sender_name=payload.name,
        recipients=[business.primary_email],
        subject=subject,
        body_text=body_text,
        body_html=None,
        attachment_metadata=[
            {
                "source": "website_form",
                "source_url": payload.source_url,
                "phone": payload.phone,
                "service": payload.service,
                "budget": payload.budget,
                "deadline": payload.deadline,
            }
        ],
        sent_at=now,
    )
    session.add(message)
    await session.flush()

    await _run_ai_intake(session, settings, business, contact, thread, message)
    await session.commit()

    await PushNotificationService(settings).send_new_inbox_message(
        session,
        business_id=business.id,
        thread_id=thread.id,
        title=f"New website enquiry for {business.name}",
        body=f"{payload.name or payload.email}: {payload.message}",
        channel="website_form",
    )
    await session.commit()

    try:
        await AlertService(settings).send_website_lead_email(
            recipient=business.primary_email,
            sender_email=str(payload.email),
            sender_name=payload.name,
            service=payload.service,
            budget=payload.budget,
            deadline=payload.deadline,
            message=payload.message,
        )
    except Exception:
        # Intake must not fail if a notification provider is temporarily down.
        logger.exception("website_lead_alert_failed", thread_id=str(thread.id))

    return WebsiteLeadResult(
        status="received",
        thread_id=str(thread.id),
        message="Website enquiry received by BeoOS",
    )


async def _get_or_create_website_form_mailbox(
    session: AsyncSession,
    business_id: UUID,
    business_slug: str,
    now: datetime,
) -> MailboxConnection:
    mailbox_email = f"website-form+{business_slug}@beoos.local"
    mailbox = await session.scalar(
        select(MailboxConnection).where(
            MailboxConnection.business_id == business_id,
            MailboxConnection.email_address == mailbox_email,
        )
    )
    if mailbox is None:
        mailbox = MailboxConnection(
            business_id=business_id,
            provider="website_form",
            email_address=mailbox_email,
            provider_account_id=business_slug,
            history_start_at=now - timedelta(days=365),
            active=True,
        )
        session.add(mailbox)
        await session.flush()
    return mailbox


async def _get_or_create_contact(
    session: AsyncSession,
    business_id: UUID,
    payload: WebsiteLeadSubmission,
) -> Contact:
    email = str(payload.email).lower()
    contact = await session.scalar(
        select(Contact).where(Contact.business_id == business_id, Contact.email == email)
    )
    if contact is None:
        contact = Contact(
            business_id=business_id,
            email=email,
            name=payload.name,
            phone=payload.phone,
        )
        session.add(contact)
        await session.flush()
    else:
        if payload.name and not contact.name:
            contact.name = payload.name
        if payload.phone and not contact.phone:
            contact.phone = payload.phone
    return contact


async def _run_ai_intake(
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
                body_text=(
                    f"Website form submission received. Add a {provider_name} key to let BeoOS "
                    "classify and draft contextual replies automatically."
                ),
                draft_type="manual_follow_up",
                status=DraftStatus.pending,
                auto_send_eligible=False,
                policy_reasons=[f"{provider_name} key is not configured"],
            )
        )
        return

    policy = normalized_ai_policy(business.settings)
    ai = OpenAIEmailService(settings)
    try:
        triage, response_id = await ai.triage_and_draft(
            subject=thread.subject,
            sender_email=message.sender_email,
            sender_name=message.sender_name,
            body_text=message.body_text,
            is_existing_client=contact.is_existing_client,
            recent_thread_context="",
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
                body_text="Website form submission needs manual review.",
                draft_type="manual_follow_up",
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
        "whatsapp_routing"
        if triage.recommended_action == RecommendedAction.route_whatsapp
        else "acknowledgement"
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
                "Website form submissions are queued for review until outbound sending "
                "is connected",
            ],
        )
    )
    thread.status = ThreadStatus.needs_approval
    message.processed_at = datetime.now(UTC)


def _subject(payload: WebsiteLeadSubmission) -> str:
    service = f" - {payload.service}" if payload.service else ""
    return f"Website enquiry{service}"


def _body(payload: WebsiteLeadSubmission) -> str:
    parts = [
        f"Name: {payload.name or 'Not provided'}",
        f"Email: {payload.email}",
        f"Phone: {payload.phone or 'Not provided'}",
        f"Service: {payload.service or 'Not provided'}",
        f"Budget: {payload.budget or 'Not provided'}",
        f"Deadline: {payload.deadline or 'Not provided'}",
        f"Source URL: {payload.source_url or 'Not provided'}",
        "",
        "Message:",
        payload.message,
    ]
    return "\n".join(parts)


def _whatsapp_link(number: str) -> str:
    digits = "".join(character for character in number if character.isdigit())
    return f"https://wa.me/{digits}"

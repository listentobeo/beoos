import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from email.utils import parseaddr
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.business import normalized_ai_policy
from app.domain.email import RecommendedAction
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
    ThreadCategory,
    ThreadStatus,
)
from app.services.alerts import AlertService
from app.services.approval_notifications import ApprovalNotificationService
from app.services.contact_identity import normalize_email_identity
from app.services.crypto import SecretCipher
from app.services.gmail import GmailClient, normalize_gmail_message
from app.services.openai_email import OpenAIEmailService
from app.services.policy import EmailPolicyEngine
from app.services.push_notifications import PushNotificationService
from app.services.zoho_mail import ZohoMailClient

logger = structlog.get_logger()

FORM_RELAY_ADDRESSES = {"submissions@formsubmit.co", "noreply@formsubmit.co"}
EMAIL_PATTERN = re.compile(r"[\w.!#$%&'*+/=?^`{|}~-]+@[\w.-]+\.[A-Za-z]{2,}")


@dataclass
class MailboxSyncReport:
    messages_fetched: int = 0
    messages_created: int = 0
    duplicates_skipped: int = 0

    @property
    def imported(self) -> int:
        return self.messages_created


class EmailSyncService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cipher = SecretCipher(settings.secret_encryption_key)
        self._zoho = ZohoMailClient(settings)
        self._gmail = GmailClient(settings)
        self._ai = OpenAIEmailService(settings)
        self._alerts = AlertService(settings)
        self._approval_notifications = ApprovalNotificationService(settings)

    async def sync_mailbox(
        self, session: AsyncSession, mailbox: MailboxConnection
    ) -> MailboxSyncReport:
        report = MailboxSyncReport()
        if not mailbox.provider_account_id or not mailbox.refresh_token_encrypted:
            logger.warning(
                "mailbox_sync_skipped_missing_credentials",
                mailbox_id=str(mailbox.id),
                business_id=str(mailbox.business_id),
                provider=mailbox.provider,
            )
            return report
        business = await session.get(Business, mailbox.business_id)
        if business is None:
            logger.warning(
                "mailbox_sync_skipped_missing_business",
                mailbox_id=str(mailbox.id),
                business_id=str(mailbox.business_id),
                provider=mailbox.provider,
            )
            return report

        logger.info(
            "mailbox_sync_started",
            mailbox_id=str(mailbox.id),
            business_id=str(business.id),
            provider=mailbox.provider,
            email_address=mailbox.email_address,
            provider_account_id=mailbox.provider_account_id,
        )

        if mailbox.provider == "gmail":
            return await self._sync_gmail_mailbox(session, business, mailbox, report)

        access_token = await self._valid_access_token(mailbox)
        folders = await self._zoho.get_folders(access_token, mailbox.provider_account_id)
        folder_map = {
            str(item.get("folderName", "")).lower(): str(item.get("folderId", ""))
            for item in folders
        }
        first_sync = mailbox.last_synced_at is None
        targets = (
            [("sent", Direction.outbound), ("inbox", Direction.inbound)]
            if first_sync
            else [("inbox", Direction.inbound)]
        )
        for folder_name, direction in targets:
            folder_id = folder_map.get(folder_name)
            if not folder_id:
                logger.warning(
                    "mailbox_sync_folder_missing",
                    mailbox_id=str(mailbox.id),
                    business_id=str(business.id),
                    folder_name=folder_name,
                    available_folders=list(folder_map.keys()),
                )
                continue
            start = 1
            while True:
                messages = await self._zoho.list_messages(
                    access_token=access_token,
                    account_id=mailbox.provider_account_id,
                    folder_id=folder_id,
                    start=start,
                    limit=200,
                    status=None,
                )
                report.messages_fetched += len(messages)
                logger.info(
                    "mailbox_sync_messages_fetched",
                    mailbox_id=str(mailbox.id),
                    business_id=str(business.id),
                    folder_name=folder_name,
                    direction=direction.value,
                    start=start,
                    fetched=len(messages),
                    first_sync=first_sync,
                )
                if not messages:
                    break
                reached_history_boundary = False
                for summary in messages:
                    sent_at = self._parse_zoho_time(
                        summary.get("receivedTime") or summary.get("sentDateInGMT")
                    )
                    if sent_at < mailbox.history_start_at:
                        reached_history_boundary = True
                        continue
                    provider_message_id = str(
                        summary.get("messageId") or summary.get("messageID") or ""
                    )
                    if not provider_message_id:
                        continue
                    exists = await session.scalar(
                        select(EmailMessage.id).where(
                            EmailMessage.mailbox_id == mailbox.id,
                            EmailMessage.provider_message_id == provider_message_id,
                        )
                    )
                    if exists:
                        report.duplicates_skipped += 1
                        continue
                    content = await self._zoho.get_message_content(
                        access_token=access_token,
                        account_id=mailbox.provider_account_id,
                        folder_id=folder_id,
                        message_id=provider_message_id,
                    )
                    created_thread_id = await self._import_message(
                        session,
                        business,
                        mailbox,
                        summary,
                        content,
                        direction=direction,
                    )
                    if created_thread_id:
                        report.messages_created += 1
                        if direction == Direction.inbound:
                            sender = summary.get("fromAddress") or summary.get("sender")
                            subject = summary.get("subject") or "(no subject)"
                            await PushNotificationService(self._settings).send_new_inbox_message(
                                session,
                                business_id=business.id,
                                thread_id=created_thread_id,
                                title=f"New email for {business.name}",
                                body=f"{sender}: {subject}",
                                channel="email",
                            )
                await session.commit()
                mailbox.sync_lease_until = datetime.now(UTC) + timedelta(minutes=5)
                await session.commit()
                if reached_history_boundary or len(messages) < 200:
                    break
                start += 200

        mailbox.last_synced_at = datetime.now(UTC)
        await session.commit()
        logger.info(
            "mailbox_sync_finished",
            mailbox_id=str(mailbox.id),
            business_id=str(business.id),
            provider=mailbox.provider,
            messages_fetched=report.messages_fetched,
            messages_created=report.messages_created,
            duplicates_skipped=report.duplicates_skipped,
        )
        return report

    async def _sync_gmail_mailbox(
        self,
        session: AsyncSession,
        business: Business,
        mailbox: MailboxConnection,
        report: MailboxSyncReport,
    ) -> MailboxSyncReport:
        access_token = await self._valid_access_token(mailbox)
        first_sync = mailbox.last_synced_at is None
        targets = (
            [("SENT", Direction.outbound), ("INBOX", Direction.inbound)]
            if first_sync
            else [("INBOX", Direction.inbound)]
        )
        for label_id, direction in targets:
            page_token: str | None = None
            while True:
                page = await self._gmail.list_messages(
                    access_token=access_token,
                    label_id=label_id,
                    page_token=page_token,
                    max_results=100,
                    after=mailbox.history_start_at,
                )
                entries = [
                    item for item in page.get("messages", []) if isinstance(item, dict)
                ]
                report.messages_fetched += len(entries)
                logger.info(
                    "mailbox_sync_messages_fetched",
                    mailbox_id=str(mailbox.id),
                    business_id=str(business.id),
                    provider=mailbox.provider,
                    folder_name=label_id.lower(),
                    direction=direction.value,
                    fetched=len(entries),
                    first_sync=first_sync,
                )
                for entry in entries:
                    provider_message_id = str(entry.get("id") or "")
                    if not provider_message_id:
                        continue
                    exists = await session.scalar(
                        select(EmailMessage.id).where(
                            EmailMessage.mailbox_id == mailbox.id,
                            EmailMessage.provider_message_id == provider_message_id,
                        )
                    )
                    if exists:
                        report.duplicates_skipped += 1
                        continue
                    message = await self._gmail.get_message(
                        access_token=access_token,
                        message_id=provider_message_id,
                    )
                    summary, content = normalize_gmail_message(message)
                    sent_at = self._parse_zoho_time(
                        summary.get("receivedTime") or summary.get("sentDateInGMT")
                    )
                    if sent_at < mailbox.history_start_at:
                        continue
                    created_thread_id = await self._import_message(
                        session,
                        business,
                        mailbox,
                        summary,
                        content,
                        direction=direction,
                    )
                    if created_thread_id:
                        report.messages_created += 1
                        if direction == Direction.inbound:
                            sender = summary.get("fromAddress") or summary.get("sender")
                            subject = summary.get("subject") or "(no subject)"
                            await PushNotificationService(self._settings).send_new_inbox_message(
                                session,
                                business_id=business.id,
                                thread_id=created_thread_id,
                                title=f"New Gmail message for {business.name}",
                                body=f"{sender}: {subject}",
                                channel="gmail",
                            )
                await session.commit()
                page_token = str(page.get("nextPageToken") or "")
                if not page_token:
                    break
        mailbox.last_synced_at = datetime.now(UTC)
        await session.commit()
        logger.info(
            "mailbox_sync_finished",
            mailbox_id=str(mailbox.id),
            business_id=str(business.id),
            provider=mailbox.provider,
            messages_fetched=report.messages_fetched,
            messages_created=report.messages_created,
            duplicates_skipped=report.duplicates_skipped,
        )
        return report

    async def send_approved_draft(
        self,
        session: AsyncSession,
        draft: EmailDraft,
        *,
        actor_id: str,
    ) -> None:
        source_message = await session.get(EmailMessage, draft.source_message_id)
        if source_message is None:
            raise RuntimeError("Draft source message was not found")
        mailbox = await session.get(MailboxConnection, source_message.mailbox_id)
        thread = await session.get(EmailThread, draft.thread_id)
        if mailbox is None or thread is None or not mailbox.provider_account_id:
            raise RuntimeError("Draft mailbox or thread was not found")

        draft.status = DraftStatus.approved
        draft.approved_by = actor_id
        await session.commit()
        try:
            provider_id = await self._reply(
                mailbox=mailbox,
                source_message=source_message,
                subject=draft.subject,
                body=draft.body_text,
            )
        except Exception:
            draft.status = DraftStatus.failed
            await session.commit()
            raise
        now = datetime.now(UTC)
        draft.status = DraftStatus.sent
        draft.approved_by = actor_id
        draft.sent_at = now
        draft.provider_message_id = provider_id
        thread.status = (
            ThreadStatus.routed_whatsapp
            if draft.draft_type == "whatsapp_routing"
            else ThreadStatus.acknowledged
        )
        session.add(
            EmailMessage(
                thread_id=thread.id,
                mailbox_id=mailbox.id,
                provider_message_id=provider_id,
                direction=Direction.outbound,
                sender_email=mailbox.email_address,
                recipients=[source_message.sender_email],
                subject=draft.subject,
                body_text=draft.body_text,
                sent_at=now,
                processed_at=now,
            )
        )
        session.add(
            AuditLog(
                business_id=thread.business_id,
                actor_id=actor_id,
                action="email_draft.approved_and_sent",
                resource_type="email_draft",
                resource_id=str(draft.id),
                details={"provider_message_id": provider_id},
            )
        )
        await session.commit()

    async def _import_message(
        self,
        session: AsyncSession,
        business: Business,
        mailbox: MailboxConnection,
        summary: dict[str, Any],
        content: dict[str, Any],
        *,
        direction: Direction,
    ) -> UUID | None:
        content_data = content.get("data", content)
        body_html = str(content_data.get("content") or content_data.get("htmlContent") or "")
        body_text = str(content_data.get("plainText") or self._html_to_text(body_html))
        attachments = content_data.get("attachments") or summary.get("attachments") or []
        attachment_metadata = attachments if isinstance(attachments, list) else []
        contact_source = (
            summary.get("fromAddress") or summary.get("sender")
            if direction == Direction.inbound
            else summary.get("toAddress") or summary.get("receiver")
        )
        contact_name, parsed_contact_email = parseaddr(str(contact_source or ""))
        contact_email = normalize_email_identity(parsed_contact_email)
        if not contact_email:
            return None
        submitted_contact = _extract_formsubmit_contact(
            body_text=body_text,
            body_html=body_html,
            sender_email=contact_email,
            summary=summary,
            excluded_emails={
                business.primary_email.lower(),
                mailbox.email_address.lower(),
                self._settings.alert_from_email.lower(),
            },
        )
        if direction == Direction.inbound and submitted_contact:
            contact_email = normalize_email_identity(submitted_contact["email"])
            contact_name = submitted_contact.get("name") or contact_name
            relay_sender = normalize_email_identity(parseaddr(str(contact_source or ""))[1])
            attachment_metadata = [
                *attachment_metadata,
                {
                    "source": "formsubmit_email",
                    "relay_sender": relay_sender,
                    "reply_to_email": contact_email,
                    "reply_to_name": contact_name,
                    "reply_to_phone": submitted_contact.get("phone", ""),
                },
            ]
        if (
            direction == Direction.inbound
            and contact_email == self._settings.alert_from_email.lower()
        ):
            return None

        contact = await session.scalar(
            select(Contact).where(
                Contact.business_id == business.id,
                Contact.email == contact_email,
            )
        )
        if contact is None:
            contact = Contact(
                business_id=business.id,
                email=contact_email,
                name=contact_name or None,
            )
            session.add(contact)
            await session.flush()
        elif contact_name and not contact.name:
            contact.name = contact_name
        if submitted_contact and submitted_contact.get("phone") and not contact.phone:
            contact.phone = submitted_contact["phone"]
        if direction == Direction.outbound:
            contact.is_existing_client = True

        provider_thread_id = str(
            summary.get("threadId") or summary.get("messageId") or summary.get("messageID")
        )
        thread = await session.scalar(
            select(EmailThread).where(
                EmailThread.business_id == business.id,
                EmailThread.provider_thread_id == provider_thread_id,
            )
        )
        sent_at = self._parse_zoho_time(summary.get("receivedTime") or summary.get("sentDateInGMT"))
        subject = str(summary.get("subject") or "(no subject)")
        if thread is None:
            thread = EmailThread(
                business_id=business.id,
                contact_id=contact.id,
                provider_thread_id=provider_thread_id,
                subject=subject,
                latest_message_at=sent_at,
                unread_count=1 if direction == Direction.inbound else 0,
            )
            session.add(thread)
            await session.flush()
        else:
            thread.latest_message_at = max(thread.latest_message_at, sent_at)
            if direction == Direction.inbound:
                thread.unread_count += 1

        message = EmailMessage(
            thread_id=thread.id,
            mailbox_id=mailbox.id,
            provider_message_id=str(summary.get("messageId") or summary.get("messageID")),
            direction=direction,
            sender_email=(
                contact_email if direction == Direction.inbound else mailbox.email_address
            ),
            sender_name=contact_name or None if direction == Direction.inbound else business.name,
            recipients=(
                [mailbox.email_address] if direction == Direction.inbound else [contact_email]
            ),
            subject=subject,
            body_text=body_text,
            body_html=body_html or None,
            attachment_metadata=attachment_metadata,
            sent_at=sent_at,
        )
        session.add(message)
        await session.flush()

        is_recent = sent_at >= datetime.now(UTC) - timedelta(minutes=15)
        if direction == Direction.outbound or not is_recent:
            message.processed_at = datetime.now(UTC)
            thread.category = (
                ThreadCategory.existing_client if contact.is_existing_client else thread.category
            )
            return thread.id

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
        triage, response_id = await self._ai.triage_and_draft(
            subject=subject,
            sender_email=contact_email,
            sender_name=contact_name or None,
            body_text=body_text,
            is_existing_client=contact.is_existing_client,
            recent_thread_context=recent_context,
            business_name=business.name,
            reply_signature=business.reply_signature,
            whatsapp_link=self._whatsapp_link(business.whatsapp_number),
            business_policy_instructions=policy.custom_instructions,
        )
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
                model=self._settings.effective_ai_model,
                response_id=response_id,
            )
        )

        thread.category = (
            ThreadCategory.existing_client if contact.is_existing_client else triage.category
        )
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
        draft = EmailDraft(
            thread_id=thread.id,
            source_message_id=message.id,
            subject=triage.acknowledgement_subject,
            body_text=triage.acknowledgement_body,
            draft_type=draft_type,
            auto_send_eligible=decision.allowed,
            policy_reasons=decision.reasons,
        )
        session.add(draft)
        message.processed_at = datetime.now(UTC)

        if decision.allowed and is_recent:
            draft.status = DraftStatus.approved
            await session.commit()
            try:
                provider_id = await self._reply(
                    mailbox=mailbox,
                    source_message=message,
                    subject=draft.subject,
                    body=draft.body_text,
                )
            except Exception:
                draft.status = DraftStatus.failed
                thread.status = ThreadStatus.needs_approval
                draft.policy_reasons = [*draft.policy_reasons, "Zoho delivery failed"]
                await session.commit()
                raise
            now = datetime.now(UTC)
            draft.status = DraftStatus.sent
            draft.sent_at = now
            draft.provider_message_id = provider_id
            thread.status = (
                ThreadStatus.routed_whatsapp
                if draft_type == "whatsapp_routing"
                else ThreadStatus.acknowledged
            )
            session.add(
                EmailMessage(
                    thread_id=thread.id,
                    mailbox_id=mailbox.id,
                    provider_message_id=provider_id,
                    direction=Direction.outbound,
                    sender_email=mailbox.email_address,
                    recipients=[message.sender_email],
                    subject=draft.subject,
                    body_text=draft.body_text,
                    sent_at=now,
                    processed_at=now,
                )
            )
            session.add(
                AuditLog(
                    business_id=business.id,
                    actor_id="system",
                    action="email_acknowledgement.auto_sent",
                    resource_type="email_draft",
                    resource_id=str(draft.id),
                    details={"provider_message_id": provider_id},
                )
            )
        else:
            thread.status = ThreadStatus.needs_approval
            await self._approval_notifications.notify_needs_approval(
                session,
                business_id=business.id,
                thread_id=thread.id,
                reason="Mailbox reply draft is waiting for review",
            )

        if triage.urgency:
            try:
                await self._alerts.send_urgent_email(
                    recipient=business.primary_email,
                    thread_subject=subject,
                    sender_email=contact_email,
                )
            except Exception:
                logger.exception("urgent_alert_failed", thread_id=str(thread.id))

        return thread.id

    async def _valid_access_token(self, mailbox: MailboxConnection) -> str:
        now = datetime.now(UTC)
        if (
            mailbox.access_token_encrypted
            and mailbox.token_expires_at
            and mailbox.token_expires_at > now + timedelta(seconds=30)
        ):
            return self._cipher.decrypt(mailbox.access_token_encrypted)
        if not mailbox.refresh_token_encrypted:
            raise RuntimeError(f"{mailbox.provider} refresh token is missing")
        refresh_token = self._cipher.decrypt(mailbox.refresh_token_encrypted)
        if mailbox.provider == "gmail":
            token, expires_at = await self._gmail.refresh_access_token(refresh_token)
        else:
            token, expires_at = await self._zoho.refresh_access_token(refresh_token)
        mailbox.access_token_encrypted = self._cipher.encrypt(token)
        mailbox.token_expires_at = expires_at
        return token

    async def _reply(
        self,
        *,
        mailbox: MailboxConnection,
        source_message: EmailMessage,
        subject: str,
        body: str,
    ) -> str:
        access_token = await self._valid_access_token(mailbox)
        direct_reply_email = _direct_reply_email(source_message)
        if direct_reply_email and mailbox.provider == "zoho":
            return await self._zoho.send_email(
                access_token=access_token,
                account_id=mailbox.provider_account_id or "",
                from_address=mailbox.email_address,
                to_address=direct_reply_email,
                subject=subject,
                body=body,
            )
        if mailbox.provider == "gmail":
            return await self._gmail.reply(
                access_token=access_token,
                message_id=source_message.provider_message_id,
                to=direct_reply_email or source_message.sender_email,
                subject=subject,
                body=body,
            )
        return await self._zoho.reply(
            access_token=access_token,
            account_id=mailbox.provider_account_id or "",
            message_id=source_message.provider_message_id,
            body=body,
        )

    async def close(self) -> None:
        await self._zoho.close()
        await self._gmail.close()
        await self._ai.close()

    @staticmethod
    def _parse_zoho_time(value: object) -> datetime:
        if value is None:
            return datetime.now(UTC)
        text = str(value)
        if text.isdigit():
            number = int(text)
            if number > 10_000_000_000:
                number //= 1000
            return datetime.fromtimestamp(number, tz=UTC)
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return datetime.now(UTC)

    @staticmethod
    def _html_to_text(value: str) -> str:
        without_tags = re.sub(r"<[^>]+>", " ", value)
        return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()

    @staticmethod
    def _whatsapp_link(number: str) -> str:
        digits = "".join(character for character in number if character.isdigit())
        return f"https://wa.me/{digits}"


def _extract_formsubmit_contact(
    *,
    body_text: str,
    body_html: str,
    sender_email: str,
    summary: dict[str, Any],
    excluded_emails: set[str] | None = None,
) -> dict[str, str] | None:
    if sender_email not in FORM_RELAY_ADDRESSES and "formsubmit" not in sender_email:
        return None
    excluded = {normalize_email_identity(email) for email in excluded_emails or set()}
    combined = "\n".join(
        value
        for value in [
            str(summary.get("subject") or ""),
            body_text,
            EmailSyncService._html_to_text(body_html),
        ]
        if value
    )
    candidates = [
        normalize_email_identity(email)
        for email in EMAIL_PATTERN.findall(combined)
        if normalize_email_identity(email)
        and normalize_email_identity(email) not in FORM_RELAY_ADDRESSES
        and normalize_email_identity(email) not in excluded
        and "formsubmit" not in normalize_email_identity(email)
        and "beoos.local" not in normalize_email_identity(email)
    ]
    if not candidates:
        return None
    email = candidates[0]
    return {
        "email": email,
        "name": _extract_labeled_value(combined, ["name", "full name", "client name"]),
        "phone": _extract_labeled_value(
            combined,
            ["phone", "phone number", "whatsapp", "whatsapp number", "mobile"],
        ),
    }


def _extract_labeled_value(text: str, labels: list[str]) -> str:
    for label in labels:
        pattern = re.compile(rf"(?im)^\s*{re.escape(label)}\s*[:=-]\s*(.+?)\s*$")
        match = pattern.search(text)
        if match:
            value = match.group(1).strip()
            if value and not EMAIL_PATTERN.fullmatch(value):
                return value[:160]
    return ""


def _direct_reply_email(source_message: EmailMessage) -> str:
    for attachment in source_message.attachment_metadata or []:
        if not isinstance(attachment, dict):
            continue
        if attachment.get("source") != "formsubmit_email":
            continue
        reply_to = str(attachment.get("reply_to_email") or "").strip().lower()
        if reply_to and reply_to != source_message.sender_email.lower():
            return reply_to
    return ""





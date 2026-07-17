import asyncio

import resend

from app.core.config import Settings


class AlertService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        resend.api_key = settings.resend_api_key

    async def send_urgent_email(
        self,
        *,
        recipient: str,
        thread_subject: str,
        sender_email: str,
    ) -> None:
        if not self._settings.resend_api_key:
            return

        def send() -> None:
            resend.Emails.send(
                {
                    "from": self._settings.alert_from_email,
                    "to": [recipient],
                    "subject": f"[BeoOS Urgent] {thread_subject}",
                    "text": (
                        f"BeoOS flagged an urgent email from {sender_email}.\n\n"
                        "Open the Urgent section in BeoOS to review it."
                    ),
                    "headers": {"X-BeoOS-System": "urgent-alert"},
                }
            )

        await asyncio.to_thread(send)

    async def send_website_lead_email(
        self,
        *,
        recipient: str,
        sender_email: str,
        sender_name: str | None,
        service: str | None,
        budget: str | None,
        deadline: str | None,
        message: str,
    ) -> None:
        if not self._settings.resend_api_key:
            return

        def send() -> None:
            resend.Emails.send(
                {
                    "from": self._settings.alert_from_email,
                    "to": [recipient],
                    "subject": f"[BeoOS Lead] Website enquiry from {sender_name or sender_email}",
                    "text": (
                        "A new website form enquiry entered BeoOS.\n\n"
                        f"Name: {sender_name or 'Not provided'}\n"
                        f"Email: {sender_email}\n"
                        f"Service: {service or 'Not provided'}\n"
                        f"Budget: {budget or 'Not provided'}\n"
                        f"Deadline: {deadline or 'Not provided'}\n\n"
                        f"Message:\n{message[:1800]}\n\n"
                        "Open BeoOS Inbox to review and handle it."
                    ),
                    "headers": {"X-BeoOS-System": "website-lead-alert"},
                }
            )

        await asyncio.to_thread(send)

    async def send_needs_approval_email(
        self,
        *,
        recipient: str,
        business_name: str,
        thread_subject: str,
        reason: str,
        url: str,
    ) -> None:
        if not self._settings.resend_api_key:
            return

        def send() -> None:
            resend.Emails.send(
                {
                    "from": self._settings.alert_from_email,
                    "to": [recipient],
                    "subject": f"[BeoOS Approval] {thread_subject}",
                    "text": (
                        f"{business_name} has a message waiting for approval in BeoOS.\n\n"
                        f"Conversation: {thread_subject}\n"
                        f"Reason: {reason}\n\n"
                        f"Open approvals: {url}\n\n"
                        "Nothing has been sent to the client yet."
                    ),
                    "headers": {"X-BeoOS-System": "approval-alert"},
                }
            )

        await asyncio.to_thread(send)

    async def send_daily_report_email(
        self,
        *,
        recipient: str,
        subject: str,
        text: str,
    ) -> bool:
        if not self._settings.resend_api_key:
            return False

        def send() -> None:
            resend.Emails.send(
                {
                    "from": self._settings.alert_from_email,
                    "to": [recipient],
                    "subject": subject,
                    "text": text,
                    "headers": {"X-BeoOS-System": "daily-report"},
                }
            )

        await asyncio.to_thread(send)
        return True

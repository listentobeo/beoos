import html
import re

from app.domain.email import EmailTriageResult, RecommendedAction
from app.infrastructure.models import ThreadCategory

CODE_PATTERNS = [
    re.compile(
        r"\b\d{4,8}\b\s+(?:is\s+)?(?:your\s+)?"
        r"(?:verification|login|sign[- ]?in|otp)\s+code",
        re.I,
    ),
    re.compile(r"(?:verification|login|sign[- ]?in|otp)\s+code\s*(?:is|:)?\s*\b\d{4,8}\b", re.I),
]

NOISE_SUBJECT_PATTERNS = [
    re.compile(r"\bverification code\b", re.I),
    re.compile(r"\bsecurity code\b", re.I),
    re.compile(r"\bsign[- ]?in code\b", re.I),
    re.compile(r"\botp\b", re.I),
    re.compile(r"\bdelivery status notification\b", re.I),
    re.compile(r"\bundeliver(?:ed|able)\b", re.I),
    re.compile(r"\bmail delivery\b", re.I),
]

NOISE_SENDER_PARTS = {
    "mailer-daemon",
    "postmaster",
    "notifications@",
    "no-reply@",
    "noreply@",
}


def clean_message_text(value: str) -> str:
    text = html.unescape(str(value or ""))
    text = text.replace("\xa0", " ")
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S{90,}", "[long link removed]", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_obvious_noise(
    *,
    subject: str,
    sender_email: str,
    body_text: str,
    business_email: str,
) -> bool:
    sender = sender_email.lower()
    subject_value = subject.strip()
    combined = f"{subject_value}\n{body_text[:1200]}"
    if sender == business_email.lower():
        return False
    if any(pattern.search(subject_value) for pattern in NOISE_SUBJECT_PATTERNS):
        return True
    if any(pattern.search(combined) for pattern in CODE_PATTERNS):
        return True
    if any(part in sender for part in NOISE_SENDER_PARTS) and any(
        word in combined.lower()
        for word in ("verification", "security code", "login code", "sign-in code", "otp")
    ):
        return True
    return False


def should_skip_ai_draft(triage: EmailTriageResult) -> bool:
    return (
        triage.category == ThreadCategory.spam
        or triage.recommended_action == RecommendedAction.ignore
    )

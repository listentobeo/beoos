from datetime import timedelta

from app.domain.failures import FailureCategory

RETRYABLE_FAILURES = {
    "rate_limit",
    "timeout",
    "provider_unavailable",
    "payment_pending",
}


def classify_failure(exc: Exception, *, external_state_uncertain: bool = False) -> FailureCategory:
    if external_state_uncertain:
        return "external_action_unknown"
    name = exc.__class__.__name__.lower()
    message = str(exc).lower()
    if isinstance(exc, PermissionError):
        return "authorization"
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, ValueError):
        return "validation"
    if "auth" in name or "401" in message:
        return "authentication"
    if "429" in message or "rate" in message:
        return "rate_limit"
    if any(item in message for item in ("unavailable", "502", "503", "504")):
        return "provider_unavailable"
    return "permanent_failure"


def retry_delay(category: FailureCategory, attempt: int) -> timedelta | None:
    if category not in RETRYABLE_FAILURES:
        return None
    base = 30 if category == "rate_limit" else 5
    return timedelta(seconds=min(1800, base * (2 ** max(0, attempt - 1))))


def recovery_message(category: FailureCategory) -> str:
    messages = {
        "authentication": "Reconnect the provider before retrying.",
        "authorization": "Your role or tool permission does not allow this action.",
        "validation": "Review the input and correct the highlighted fields.",
        "rate_limit": "The provider is busy; BeoOS can retry after the backoff period.",
        "timeout": "The provider timed out; confirm its state before retrying an external action.",
        "provider_unavailable": "The provider is unavailable; the action is safely queued.",
        "malformed_output": "The AI response was invalid and no external action was taken.",
        "missing_context": "Required business information is missing.",
        "duplicate_event": "The duplicate was ignored using its idempotency key.",
        "external_action_unknown": "Do not retry until the provider state is reconciled.",
        "payment_pending": "Payment is pending provider confirmation.",
        "permanent_failure": "The action cannot be retried without an explicit correction.",
        "human_timeout": "The approval expired without execution.",
    }
    return messages[category]

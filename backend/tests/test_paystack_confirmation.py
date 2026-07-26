import hashlib
import hmac
from pathlib import Path

from app.core.config import Settings
from app.infrastructure.models import PaymentTransaction, PaymentWebhookEvent
from app.services.payments import PAYMENT_WORKFLOW_KEY
from app.services.paystack import PaystackService

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database" / "migrations" / "versions" / "20260726_0026_paystack_transactions.py"


def test_paystack_webhook_signature_is_hmac_sha512() -> None:
    settings = Settings(paystack_secret_key="test-secret")
    body = b'{"event":"charge.success"}'
    signature = hmac.new(b"test-secret", body, hashlib.sha512).hexdigest()
    service = PaystackService(settings)
    assert service.verify_webhook_signature(body, signature) is True
    assert service.verify_webhook_signature(body + b"x", signature) is False


def test_payment_records_and_deterministic_workflow_exist() -> None:
    assert PaymentTransaction.__tablename__ == "payment_transactions"
    assert PaymentWebhookEvent.__tablename__ == "payment_webhook_events"
    assert PAYMENT_WORKFLOW_KEY == "paystack_quote_payment_v1"


def test_payment_migration_enforces_tenant_and_idempotency() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "uq_payment_provider_reference" in migration
    assert "uq_payment_webhook_event" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "cross-tenant payment reference" in migration

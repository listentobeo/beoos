from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models import (
    AuditLog,
    Outcome,
    PaymentTransaction,
    Quote,
    WorkflowDefinition,
    WorkflowRun,
)

PAYMENT_WORKFLOW_KEY = "paystack_quote_payment_v1"


async def create_pending_payment(
    session: AsyncSession,
    *,
    business_id: UUID,
    quote: Quote,
    reference: str,
    authorization_url: str,
    actor_id: str,
) -> PaymentTransaction:
    existing = await session.scalar(
        select(PaymentTransaction).where(
            PaymentTransaction.provider == "paystack",
            PaymentTransaction.provider_reference == reference,
        )
    )
    if existing:
        return existing
    definition = await _payment_definition(session, business_id, actor_id)
    run = WorkflowRun(
        business_id=business_id,
        workflow_definition_id=definition.id,
        workflow_version=definition.version,
        trigger_type="payment_link",
        trigger_reference_type="quote",
        trigger_reference_id=str(quote.id),
        correlation_id=f"payment:{reference}",
        idempotency_key=reference,
        status="running",
        started_at=datetime.now(UTC),
        run_metadata={"quote_id": str(quote.id), "provider": "paystack"},
        initiated_by_user_id=actor_id,
    )
    session.add(run)
    await session.flush()
    transaction = PaymentTransaction(
        business_id=business_id,
        quote_id=quote.id,
        workflow_run_id=run.id,
        provider="paystack",
        provider_reference=reference,
        amount=quote.deposit_required or Decimal("0"),
        currency=quote.currency,
        status="pending",
        provider_status="initialized",
        authorization_url=authorization_url,
    )
    session.add(transaction)
    await session.flush()
    return transaction


async def apply_paystack_status(
    session: AsyncSession,
    transaction: PaymentTransaction,
    provider_data: dict[str, Any],
    *,
    actor_id: str,
) -> bool:
    validate_paystack_evidence(
        provider_data,
        reference=transaction.provider_reference,
        amount=transaction.amount,
        currency=transaction.currency,
    )
    provider_status = str(provider_data.get("status") or "").lower()
    transaction.verification_attempts += 1
    transaction.last_verified_at = datetime.now(UTC)
    transaction.provider_status = provider_status
    transaction.provider_transaction_id = str(provider_data.get("id") or "") or None
    transaction.channel = str(provider_data.get("channel") or "") or None
    transaction.provider_payload = _safe_provider_payload(provider_data)
    if provider_status != "success":
        transaction.status = "pending" if provider_status in {"pending", "ongoing"} else "failed"
        return False
    if transaction.status == "confirmed":
        return True
    transaction.status = "confirmed"
    transaction.paid_at = _paid_at(provider_data)
    run = await session.get(WorkflowRun, transaction.workflow_run_id)
    if run:
        run.status = "completed"
        run.completed_at = datetime.now(UTC)
    outcome = Outcome(
        business_id=transaction.business_id,
        workflow_run_id=transaction.workflow_run_id,
        outcome_type="deposit_paid",
        status="confirmed",
        value_numeric=transaction.amount,
        value_currency=transaction.currency,
        value_text=transaction.provider_reference,
        source="paystack_verified",
        recorded_by=actor_id,
        observed_at=transaction.paid_at or datetime.now(UTC),
        confidence=Decimal("1"),
        outcome_metadata={
            "quote_id": str(transaction.quote_id),
            "payment_transaction_id": str(transaction.id),
        },
    )
    session.add(outcome)
    await session.flush()
    transaction.outcome_id = outcome.id
    session.add(
        AuditLog(
            business_id=transaction.business_id,
            actor_id=actor_id,
            action="payment.confirmed",
            resource_type="payment_transaction",
            resource_id=str(transaction.id),
            details={
                "quote_id": str(transaction.quote_id),
                "reference": transaction.provider_reference,
                "source": "paystack_verified",
            },
        )
    )
    return True


def validate_paystack_evidence(
    provider_data: dict[str, Any],
    *,
    reference: str,
    amount: Decimal,
    currency: str,
) -> None:
    if str(provider_data.get("reference") or "") != reference:
        raise ValueError("Paystack reference mismatch")
    amount_minor = int(provider_data.get("amount") or 0)
    expected_minor = int((amount * Decimal("100")).quantize(Decimal("1")))
    provider_currency = str(provider_data.get("currency") or "").upper()
    if amount_minor != expected_minor or provider_currency != currency.upper():
        raise ValueError("Paystack amount or currency mismatch")


async def _payment_definition(
    session: AsyncSession, business_id: UUID, actor_id: str
) -> WorkflowDefinition:
    definition = await session.scalar(
        select(WorkflowDefinition).where(
            WorkflowDefinition.business_id == business_id,
            WorkflowDefinition.key == PAYMENT_WORKFLOW_KEY,
            WorkflowDefinition.version == 1,
        )
    )
    if definition:
        return definition
    definition = WorkflowDefinition(
        business_id=business_id,
        key=PAYMENT_WORKFLOW_KEY,
        name="Paystack quote payment confirmation",
        description="Provider-verified deposit confirmation.",
        business_objective="Confirm quote deposits without AI judgment.",
        workflow_type="deterministic",
        version=1,
        status="active",
        trigger_type="payment_link",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        configuration={"provider": "paystack", "ai_authority": False},
        policy_version="1",
        prompt_version="none",
        deployment_mode="approval_required",
        created_by=actor_id,
    )
    session.add(definition)
    await session.flush()
    return definition


def _paid_at(data: dict[str, Any]) -> datetime:
    value = data.get("paid_at") or data.get("paidAt")
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(UTC)


def _safe_provider_payload(data: dict[str, Any]) -> dict[str, Any]:
    return {
        key: data.get(key)
        for key in (
            "id",
            "reference",
            "status",
            "amount",
            "currency",
            "channel",
            "paid_at",
            "gateway_response",
        )
    }

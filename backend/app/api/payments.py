import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import BusinessAccess, require_admin, require_business_access
from app.infrastructure.database import get_session
from app.infrastructure.models import (
    AuditLog,
    PaymentTransaction,
    PaymentWebhookEvent,
)
from app.services.payments import apply_paystack_status
from app.services.paystack import PaystackService

router = APIRouter(tags=["payments"])


@router.post("/webhooks/paystack")
async def paystack_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, bool]:
    body = await request.body()
    signature = request.headers.get("x-paystack-signature")
    if not PaystackService(settings).verify_webhook_signature(body, signature):
        raise HTTPException(status_code=403, detail="Invalid Paystack webhook signature")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook JSON") from exc
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Missing Paystack event data")
    reference = str(data.get("reference") or "")
    transaction = await session.scalar(
        select(PaymentTransaction).where(
            PaymentTransaction.provider == "paystack",
            PaymentTransaction.provider_reference == reference,
        )
    )
    if transaction is None:
        raise HTTPException(status_code=404, detail="Payment transaction not found")
    event_type = str(payload.get("event") or "unknown")
    event_key = f"{event_type}:{data.get('id')}:{reference}"
    payload_hash = hashlib.sha256(body).hexdigest()
    existing = await session.scalar(
        select(PaymentWebhookEvent).where(
            PaymentWebhookEvent.provider == "paystack",
            PaymentWebhookEvent.event_key == event_key,
        )
    )
    if existing:
        if existing.payload_hash != payload_hash:
            raise HTTPException(status_code=409, detail="Webhook event payload changed")
        return {"received": True}
    event = PaymentWebhookEvent(
        business_id=transaction.business_id,
        payment_transaction_id=transaction.id,
        provider="paystack",
        event_key=event_key,
        event_type=event_type,
        payload_hash=payload_hash,
        status="processing",
    )
    session.add(event)
    try:
        await apply_paystack_status(
            session,
            transaction,
            data,
            actor_id="system:paystack_webhook",
        )
        event.status = "processed"
        event.processed_at = datetime.now(UTC)
    except ValueError as exc:
        event.status = "rejected"
        await session.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await session.commit()
    return {"received": True}


@router.get("/businesses/{business_id}/payments")
async def list_payments(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    rows = (
        await session.scalars(
            select(PaymentTransaction)
            .where(PaymentTransaction.business_id == business_id)
            .order_by(PaymentTransaction.created_at.desc())
        )
    ).all()
    return [_payment_view(row) for row in rows]


@router.post("/businesses/{business_id}/payments/{payment_id}/reconcile")
async def reconcile_payment(
    business_id: UUID,
    payment_id: UUID,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    transaction = await session.scalar(
        select(PaymentTransaction).where(
            PaymentTransaction.id == payment_id,
            PaymentTransaction.business_id == business_id,
        )
    )
    if transaction is None:
        raise HTTPException(status_code=404, detail="Payment transaction not found")
    data = await PaystackService(settings).verify_transaction(transaction.provider_reference)
    await apply_paystack_status(
        session,
        transaction,
        data,
        actor_id=access.user_id,
    )
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="payment.reconciled",
            resource_type="payment_transaction",
            resource_id=str(transaction.id),
            details={"provider_status": transaction.provider_status},
        )
    )
    await session.commit()
    return _payment_view(transaction)


def _payment_view(row: PaymentTransaction) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "quote_id": str(row.quote_id),
        "provider": row.provider,
        "reference": row.provider_reference,
        "amount": str(row.amount),
        "currency": row.currency,
        "status": row.status,
        "provider_status": row.provider_status,
        "channel": row.channel,
        "paid_at": row.paid_at,
        "last_verified_at": row.last_verified_at,
        "verification_attempts": row.verification_attempts,
        "outcome_id": str(row.outcome_id) if row.outcome_id else None,
    }

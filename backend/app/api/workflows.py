from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import BusinessAccess, require_admin
from app.domain.beo_enquiry import EnquiryOutcomeCreate, ManualCommissionEnquiryCreate
from app.infrastructure.database import get_session
from app.infrastructure.models import (
    AuditLog,
    Contact,
    Direction,
    EmailMessage,
    EmailThread,
    MailboxConnection,
    Outcome,
    WorkflowRun,
)
from app.services.durable_jobs import MANUAL_AI_JOB, enqueue_job

router = APIRouter(prefix="/businesses/{business_id}/workflows", tags=["workflows"])


@router.post("/beo-commission/manual", status_code=202)
async def create_manual_commission_enquiry(
    business_id: UUID,
    payload: ManualCommissionEnquiryCreate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    email = payload.customer_email.strip().lower()
    contact = await session.scalar(
        select(Contact).where(Contact.business_id == business_id, Contact.email == email)
    )
    if contact is None:
        contact = Contact(
            business_id=business_id,
            email=email,
            name=payload.customer_name,
            phone=payload.customer_phone,
            preferred_channel="email",
        )
        session.add(contact)
        await session.flush()
    mailbox_email = f"manual-{business_id}@beoos.local"
    mailbox = await session.scalar(
        select(MailboxConnection).where(
            MailboxConnection.business_id == business_id,
            MailboxConnection.email_address == mailbox_email,
        )
    )
    if mailbox is None:
        mailbox = MailboxConnection(
            business_id=business_id,
            provider="manual",
            email_address=mailbox_email,
            history_start_at=datetime.now(UTC),
            active=True,
        )
        session.add(mailbox)
        await session.flush()
    reference = uuid4().hex
    now = datetime.now(UTC)
    thread = EmailThread(
        business_id=business_id,
        contact_id=contact.id,
        provider_thread_id=f"manual:{reference}",
        subject=f"Manual commission enquiry - {payload.requested_service or 'general'}",
        latest_message_at=now,
        unread_count=1,
    )
    session.add(thread)
    await session.flush()
    body = "\n".join(
        [
            f"Requested service: {payload.requested_service or 'Not provided'}",
            f"Budget: {payload.budget or 'Not provided'}",
            f"Deadline: {payload.deadline or 'Not provided'}",
            "",
            payload.message,
        ]
    )
    message = EmailMessage(
        thread_id=thread.id,
        mailbox_id=mailbox.id,
        provider_message_id=f"manual:{reference}",
        direction=Direction.inbound,
        sender_email=contact.email,
        sender_name=contact.name,
        recipients=[mailbox.email_address],
        subject=thread.subject,
        body_text=body,
        attachment_metadata=payload.attachments,
        sent_at=now,
    )
    session.add(message)
    await session.flush()
    job = await enqueue_job(
        session,
        business_id=business_id,
        job_type=MANUAL_AI_JOB,
        payload={
            "contact_id": str(contact.id),
            "thread_id": str(thread.id),
            "message_id": str(message.id),
        },
        idempotency_key=f"manual:{message.id}",
    )
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="manual_enquiry.accepted",
            resource_type="email_message",
            resource_id=str(message.id),
            details={"job_id": str(job.id), "workflow_key": "beo_art_commission_enquiry_v1"},
        )
    )
    await session.commit()
    return {
        "status": "accepted",
        "job_id": str(job.id),
        "thread_id": str(thread.id),
        "message_id": str(message.id),
    }


@router.post("/runs/{run_id}/outcomes", status_code=201)
async def record_enquiry_outcome(
    business_id: UUID,
    run_id: UUID,
    payload: EnquiryOutcomeCreate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    run = await session.scalar(
        select(WorkflowRun).where(
            WorkflowRun.id == run_id,
            WorkflowRun.business_id == business_id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    outcome = Outcome(
        business_id=business_id,
        workflow_run_id=run.id,
        outcome_type=payload.outcome_type,
        status=payload.status,
        value_numeric=payload.value_numeric,
        value_currency=payload.value_currency,
        value_text=payload.value_text,
        source=payload.source,
        recorded_by=access.user_id,
        observed_at=payload.observed_at,
        confidence=payload.confidence,
        outcome_metadata=payload.metadata,
    )
    session.add(outcome)
    await session.flush()
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="workflow.outcome_recorded",
            resource_type="outcome",
            resource_id=str(outcome.id),
            details={"workflow_run_id": str(run.id), "outcome_type": outcome.outcome_type},
        )
    )
    await session.commit()
    return {"id": str(outcome.id), "outcome_type": outcome.outcome_type}

"""Optional real PostgreSQL release smoke test, using a disposable database.

Set BEOOS_TEST_POSTGRES_URL to a test server's admin URL. The test creates and
drops its own database; it never migrates the database named in that URL.
"""

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import asyncpg
import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import AuthenticatedUser, require_user
from app.infrastructure.database import get_session
from app.infrastructure.models import (
    AuditLog,
    Base,
    Direction,
    DurableJob,
    EmailMessage,
    EmailThread,
    ExternalActionReconciliation,
    MailboxConnection,
    OperatorConversation,
    OperatorMessage,
    Outcome,
    PaymentTransaction,
    PaymentWebhookEvent,
    ToolCall,
    ToolDefinition,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowStep,
)
from app.main import app
from app.services.durable_jobs import MANUAL_AI_JOB, WHATSAPP_CONTACTS_SYNC_JOB

ADMIN_URL = os.getenv("BEOOS_TEST_POSTGRES_URL")
BACKEND = Path(__file__).resolve().parents[1]


async def _migrate(url: str, *args: str) -> None:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "alembic",
        *args,
        cwd=BACKEND,
        env={**os.environ, "DATABASE_URL": url, "APP_ENV": "test"},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await process.communicate()
    assert process.returncode == 0, output.decode(errors="replace")


@pytest.mark.skipif(not ADMIN_URL, reason="Set BEOOS_TEST_POSTGRES_URL for real PostgreSQL tests")
async def test_upgrade_and_business_modules_against_real_postgres() -> None:
    assert ADMIN_URL is not None
    admin_url = make_url(ADMIN_URL)
    database_name = f"beoos_test_{uuid4().hex}"
    admin = await asyncpg.connect(admin_url.set(drivername="postgresql").render_as_string(False))
    url = admin_url.set(drivername="postgresql+asyncpg", database=database_name).render_as_string(
        False
    )
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = "release-owner"
    business_id, other_business_id = uuid4(), uuid4()
    overrides = dict(app.dependency_overrides)

    async def test_session() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    async def test_user() -> AuthenticatedUser:
        return AuthenticatedUser(user_id=user_id, session_id="release-test-session")

    try:
        await admin.execute(f'CREATE DATABASE "{database_name}"')
        await _migrate(url, "upgrade", "20260719_0012")
        async with engine.begin() as connection:
            for identifier, slug in [
                (business_id, "release-business"),
                (other_business_id, "other"),
            ]:
                await connection.execute(
                    text(
                        "INSERT INTO businesses "
                        "(id, slug, name, primary_email, whatsapp_number, "
                        "reply_signature, timezone, settings) "
                        "VALUES (:id, :slug, :slug, 'owner@example.com', '+2348000000000', "
                        "'Owner', 'Africa/Lagos', '{}'::jsonb)"
                    ),
                    {"id": identifier, "slug": slug},
                )
            await connection.execute(
                text(
                    "INSERT INTO business_members (id, business_id, clerk_user_id, role) "
                    "VALUES (:id, :business_id, 'release-owner', 'owner')"
                ),
                {"id": uuid4(), "business_id": business_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO business_members (id, business_id, clerk_user_id, role) "
                    "VALUES (:id, :business_id, 'release-viewer', 'viewer')"
                ),
                {"id": uuid4(), "business_id": business_id},
            )
        await engine.dispose()
        await _migrate(url, "upgrade", "head")
        # Confirm the latest rollback and re-upgrade work with the actual driver.
        await _migrate(url, "downgrade", "-1")
        await _migrate(url, "upgrade", "head")
        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT count(*) FROM businesses")) == 2
            for table in Base.metadata.sorted_tables:
                # Check every mapped column against the migrated schema.
                await connection.execute(select(table).limit(0))

        app.dependency_overrides[get_session] = test_session
        app.dependency_overrides[require_user] = test_user
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            base = f"/api/v1/businesses/{business_id}"
            for suffix in [
                "/quotes",
                "/quotes/templates",
                "/prices",
                "/crm/leads",
                "/marketing/summary",
                "/marketing/connections",
                "/marketing/opportunities",
                "/marketing/experiments",
                "/value/dashboard",
                "/recovery",
                "/analytics/summary",
            ]:
                response = await client.get(base + suffix)
                assert response.status_code == 200, (suffix, response.text)
                denied = await client.get(f"/api/v1/businesses/{other_business_id}{suffix}")
                assert denied.status_code == 403, (suffix, denied.text)

            quote_response = await client.post(
                base + "/quotes",
                json={
                    "title": "Release smoke quote",
                    "template_type": "custom",
                    "input_data": {
                        "currency": "NGN",
                        "line_items": [
                            {"label": "Portrait", "quantity": "2", "unit_price": "85000"},
                        ],
                    },
                },
            )
            assert quote_response.status_code == 201, quote_response.text
            quote = quote_response.json()
            assert float(quote["total"]) == 170000
            assert (await client.get(base + f"/quotes/{quote['id']}")).status_code == 200
            assert len((await client.get(base + "/quotes")).json()) == 1
            public_token = quote["public_url"].rsplit("/", 1)[-1]
            public_path = f"/api/v1/quotes/{public_token}"
            assert (await client.get(public_path)).status_code == 200
            accepted = await client.post(public_path + "/accept")
            assert accepted.status_code == 200, accepted.text
            assert (await client.post(public_path + "/accept")).status_code == 200

            imported = await client.post(
                base + "/marketing/import",
                json={
                    "source": "search_console",
                    "rows": [
                        {
                            "page_url": "https://example.com/portraits",
                            "query": "custom portrait",
                            "impressions": 100,
                            "clicks": 4,
                        }
                    ],
                },
            )
            assert imported.status_code == 201, imported.text
            summary = (await client.get(base + "/marketing/summary")).json()
            assert sum(item["impressions"] for item in summary["totals"]) == 100
            baseline = await client.put(
                base + "/value/baseline",
                json={
                    "workflow_key": "beo_art_commission_enquiry_v1",
                    "prior_response_time_minutes": "60",
                    "currency": "NGN",
                },
            )
            assert baseline.status_code == 200, baseline.text
            dashboard = (await client.get(base + "/value/dashboard")).json()
            assert dashboard["baseline"]["source"] == "user_estimate"
            assert dashboard["evidence"]["workflow_runs"] == 0
            async with sessions() as session:
                definition = WorkflowDefinition(
                    business_id=business_id,
                    key="beo_art_commission_enquiry_v1",
                    name="Commission enquiries",
                    business_objective="Qualify enquiries",
                    workflow_type="commission",
                    trigger_type="manual",
                    created_by=user_id,
                )
                session.add(definition)
                await session.flush()
                run = WorkflowRun(
                    business_id=business_id,
                    workflow_definition_id=definition.id,
                    workflow_version=1,
                    trigger_type="manual",
                    trigger_reference_type="manual",
                    trigger_reference_id="release-test",
                    correlation_id="release-test",
                    idempotency_key="value-run",
                    status="completed",
                )
                session.add(run)
                await session.flush()
                session.add_all(
                    [
                        Outcome(
                            business_id=business_id,
                            workflow_run_id=run.id,
                            outcome_type="lead_qualified",
                            status="confirmed",
                            source="manual",
                            recorded_by=user_id,
                            observed_at=datetime.now(UTC),
                        ),
                        Outcome(
                            business_id=business_id,
                            workflow_run_id=run.id,
                            outcome_type="response_time_minutes",
                            status="confirmed",
                            value_numeric=30,
                            source="manual",
                            recorded_by=user_id,
                            observed_at=datetime.now(UTC),
                        ),
                    ]
                )
                await session.commit()
            dashboard = (await client.get(base + "/value/dashboard")).json()
            assert dashboard["evidence"]["workflow_runs"] == 1
            revenue = {item["key"]: item for item in dashboard["categories"]["revenue"]}
            assert revenue["qualified_leads"]["value"] == "1"
            speed = {item["key"]: item for item in dashboard["categories"]["speed"]}
            assert float(speed["median_first_response_time"]["value"]) == 30
            assert float(speed["median_first_response_time"]["improvement"]) == 0.5
            # Shared trigger functions must work for each table's record shape,
            # while still rejecting cross-tenant relationships.
            async with sessions() as session:
                now = datetime.now(UTC)
                mailbox = MailboxConnection(
                    business_id=business_id, email_address="owner@example.com", history_start_at=now
                )
                other_mailbox = MailboxConnection(
                    business_id=other_business_id,
                    email_address="other@example.com",
                    history_start_at=now,
                )
                thread = EmailThread(
                    business_id=business_id, provider_thread_id="test-thread", latest_message_at=now
                )
                conversation = OperatorConversation(
                    business_id=business_id, user_id=user_id, title="Smoke conversation"
                )
                transaction = PaymentTransaction(
                    business_id=business_id,
                    quote_id=quote["id"],
                    workflow_run_id=run.id,
                    provider="paystack",
                    provider_reference="test-payment",
                    amount=170000,
                    currency="NGN",
                    status="pending",
                )
                session.add_all([mailbox, other_mailbox, thread, conversation, transaction])
                await session.flush()
                session.add_all(
                    [
                        EmailMessage(
                            thread_id=thread.id,
                            mailbox_id=mailbox.id,
                            provider_message_id="message",
                            direction=Direction.inbound,
                            sender_email="client@example.com",
                            sent_at=now,
                        ),
                        OperatorMessage(
                            business_id=business_id,
                            conversation_id=conversation.id,
                            role="user",
                            content="Read my business metrics",
                        ),
                        PaymentWebhookEvent(
                            business_id=business_id,
                            payment_transaction_id=transaction.id,
                            provider="paystack",
                            event_key="test-event",
                            event_type="charge.success",
                            payload_hash="test",
                            status="processed",
                        ),
                    ]
                )
                await session.flush()
                with pytest.raises(DBAPIError, match="cross-tenant email message relationship"):
                    async with session.begin_nested():
                        session.add(
                            EmailMessage(
                                thread_id=thread.id,
                                mailbox_id=other_mailbox.id,
                                provider_message_id="wrong-tenant",
                                direction=Direction.inbound,
                                sender_email="client@example.com",
                                sent_at=now,
                            )
                        )
                        await session.flush()
                with pytest.raises(DBAPIError, match="cross-tenant operator conversation"):
                    async with session.begin_nested():
                        session.add(
                            OperatorMessage(
                                business_id=other_business_id,
                                conversation_id=conversation.id,
                                role="user",
                                content="Wrong tenant",
                            )
                        )
                        await session.flush()
                with pytest.raises(DBAPIError, match="cross-tenant payment webhook"):
                    async with session.begin_nested():
                        session.add(
                            PaymentWebhookEvent(
                                business_id=other_business_id,
                                payment_transaction_id=transaction.id,
                                provider="paystack",
                                event_key="wrong-event",
                                event_type="charge.success",
                                payload_hash="test",
                                status="processed",
                            )
                        )
                        await session.flush()
                with pytest.raises(DBAPIError, match="cross-tenant workflow run relationship"):
                    async with session.begin_nested():
                        session.add(
                            Outcome(
                                business_id=other_business_id,
                                workflow_run_id=run.id,
                                outcome_type="lead_qualified",
                                status="confirmed",
                                source="manual",
                                recorded_by=user_id,
                                observed_at=now,
                            )
                        )
                        await session.flush()
                await session.commit()

            async with sessions() as session:
                job = DurableJob(
                    business_id=business_id,
                    job_type=MANUAL_AI_JOB,
                    payload={},
                    idempotency_key="release-job",
                    status="dead_letter",
                    attempt_count=5,
                    max_attempts=5,
                    last_error="Provider unavailable",
                )
                unsafe_job = DurableJob(
                    business_id=business_id,
                    job_type=WHATSAPP_CONTACTS_SYNC_JOB,
                    payload={},
                    idempotency_key="release-unsafe-job",
                    status="dead_letter",
                    attempt_count=5,
                    max_attempts=5,
                )
                other_job = DurableJob(
                    business_id=other_business_id,
                    job_type=MANUAL_AI_JOB,
                    payload={},
                    idempotency_key="other-job",
                    status="dead_letter",
                )
                session.add_all([job, unsafe_job, other_job])
                await session.commit()
                job_id, unsafe_id, other_id = job.id, unsafe_job.id, other_job.id
            queue = (await client.get(base + "/recovery")).json()
            assert len(queue["durable_jobs"]) == 2
            response = await client.post(
                base + f"/recovery/jobs/{other_id}/decision",
                json={"action": "retry", "reason": "Provider restored"},
            )
            assert response.status_code == 404
            user_id = "release-viewer"
            response = await client.post(
                base + f"/recovery/jobs/{job_id}/decision",
                json={"action": "retry", "reason": "Provider restored"},
            )
            assert response.status_code == 403
            user_id = "release-owner"
            response = await client.post(
                base + f"/recovery/jobs/{job_id}/decision",
                json={"action": "retry", "reason": "Provider restored"},
            )
            assert response.status_code == 200, response.text
            assert response.json()["status"] == "queued"
            assert response.json()["attempt_count"] == 5
            assert response.json()["max_attempts"] == 6
            response = await client.post(
                base + f"/recovery/jobs/{unsafe_id}/decision",
                json={"action": "retry", "reason": "Provider restored"},
            )
            assert response.status_code == 409
            response = await client.post(
                base + f"/recovery/jobs/{unsafe_id}/decision",
                json={"action": "cancel", "reason": "Stop unresolved action"},
            )
            assert response.status_code == 200, response.text

            async with sessions() as session:
                unknown = ExternalActionReconciliation(
                    business_id=business_id,
                    action_type="provider_action",
                    idempotency_key="unknown-action",
                    request_hash="test",
                    failure_category="external_action_unknown",
                    status="investigating",
                    user_message="Confirm the provider state",
                )
                session.add(unknown)
                await session.commit()
                unknown_id = unknown.id
            response = await client.post(
                base + f"/recovery/reconciliations/{unknown_id}/decision",
                json={"action": "retry", "reason": "Try unknown action"},
            )
            assert response.status_code == 409
            response = await client.post(
                base + f"/recovery/reconciliations/{unknown_id}/decision",
                json={
                    "action": "mark_reconciled",
                    "reason": "Provider confirmed completion",
                    "provider_reference": "provider-confirmation",
                },
            )
            assert response.status_code == 200, response.text
            queue = (await client.get(base + "/recovery")).json()
            assert queue["durable_jobs"] == []
            assert queue["reconciliations"] == []
            async with sessions() as session:
                tool = ToolDefinition(key="smoke_read", name="Smoke read", risk_level="low")
                step = WorkflowStep(
                    business_id=business_id,
                    workflow_run_id=run.id,
                    step_key="smoke_read",
                    step_type="tool_call",
                    sequence=1,
                )
                session.add_all([tool, step])
                await session.flush()
                call = ToolCall(
                    business_id=business_id,
                    workflow_run_id=run.id,
                    workflow_step_id=step.id,
                    tool_definition_id=tool.id,
                    request_hash="smoke",
                    idempotency_key="failed-read",
                    status="failed",
                    failure_category="provider_unavailable",
                )
                session.add(call)
                await session.commit()
                call_id = call.id
            opened = await client.post(base + f"/recovery/tool-calls/{call_id}/reconciliation")
            assert opened.status_code == 201, opened.text
            reconciliation_id = opened.json()["id"]
            response = await client.post(
                base + f"/recovery/reconciliations/{reconciliation_id}/decision",
                json={"action": "retry", "reason": "No linked executor"},
            )
            assert response.status_code == 409
            response = await client.post(
                base + f"/recovery/reconciliations/{reconciliation_id}/decision",
                json={"action": "mark_failed", "reason": "Failure reviewed and closed"},
            )
            assert response.status_code == 200, response.text
            queue = (await client.get(base + "/recovery")).json()
            assert queue["tool_calls"] == []
            assert queue["reconciliations"] == []
            async with sessions() as session:
                audits = (
                    await session.scalars(
                        select(AuditLog).where(AuditLog.business_id == business_id)
                    )
                ).all()
                assert {"durable_job.retry", "durable_job.cancel", "reconciliation.decided"} <= {
                    row.action for row in audits
                }
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides)
        await engine.dispose()
        await admin.execute(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
        await admin.close()

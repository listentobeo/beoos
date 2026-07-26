# BeoOS controlled workflow developer guide

## Adding a workflow

1. Define a stable key and append-only version.
2. State the business objective, real trigger, input/output JSON schemas, and measurable outcomes.
3. Separate deterministic steps, AI judgment, policy checks, approvals, and tools.
4. Persist `WorkflowRun` and ordered `WorkflowStep` records with tenant ID, correlation ID, and
   idempotency key.
5. Store each `AIExecution` with model, prompt/policy/schema versions, structured input/output,
   context references, cost, latency, parse status, and safety flags.
6. Use durable jobs for provider work; request handlers should validate, persist, deduplicate, and
   enqueue.
7. Add trace, failure, evaluation, outcome, and tenant-isolation tests.

Never add an unversioned production workflow or use conversation history as official context.

## Adding a tool

Add a `ToolSpec` with explicit JSON schemas, risk, reversibility, approval default, minimum role,
timeout, retry policy, and failure mapping. Register a tenant-safe handler. Every handler receives
`business_id`; every referenced row must be checked against it.

Execution requires a registered enabled definition, tenant `ToolPermission`, compatible role and
workflow scope, validated constraints, request hash, and tenant-scoped idempotency key. Sanitize
stored payloads. External timeouts must enter `external_action_unknown` when provider success is
uncertain; do not blindly retry.

## Business context

Use `build_business_context`. Approved typed profiles, services, and policies are versioned
official context; approved price catalogue rows are price authority. Preserve source ID,
classification, authority, approval, effective dates, and expiry. Use embeddings only for
appropriate document retrieval, never as a replacement for relational authority.

## Approvals

Create structured `ApprovalRequest` records attached to a workflow run and step. Preserve original
and edited payloads. Check role and staff authority, financial limits, expiry, tool permission, and
idempotency again when resuming. No external action should be hidden inside an approval-creation
handler.

## Evaluation datasets and gates

Datasets are global read-only templates or tenant-owned versions. Private examples require
redaction and approval. The deterministic runner performs schema, exact-field, policy, pricing,
promise, and escalation checks before model-assisted grading. Thresholds are tenant/workflow
configuration, not global constants.

Deployment proposals must pin workflow, dataset, model, prompt, and policy versions; include a
passing report; record the approver and timestamp; and retain a rollback deployment.

## Failure handling

Use the shared categories in `domain/failures.py`. Retry only rate limits, timeouts, temporary
provider failures, or pending payments according to bounded backoff. Authentication,
authorization, validation, malformed output, missing context, permanent failure, and human timeout
need correction or escalation. Unknown external actions require reconciliation first.

## Payments

AI never determines payment state. Paystack webhooks require an HMAC-SHA512 signature using the
secret key. Resolve the transaction by the stored provider reference, then validate amount and
currency. Webhook event keys and payload hashes provide replay protection. Authenticated provider
verification is the reconciliation fallback.

## Migrations

Every tenant-owned table requires non-null `business_id`, PostgreSQL RLS, and relationship
integrity triggers where a foreign key could cross tenants. Migrations must support offline upgrade
and downgrade generation. Deploy schema before application code, then verify the migration head,
RLS policies, worker compatibility, and recovery queue.

## Required checks

From `backend`: Ruff, pytest, mypy, Alembic upgrade SQL, and downgrade SQL. From `frontend`:
TypeScript typecheck and production build. A phase cannot be called complete if new type errors,
failed migrations, or a dirty worktree are hidden.

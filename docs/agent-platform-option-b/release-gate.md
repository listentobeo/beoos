# BeoOS Option B final release gate

Reviewed on 26 July 2026 against revision `3c075b9` plus the Phase 19 and Phase 20
changes.

## Decision

**Source release gate: pass. Production launch gate: no-go pending live evidence.**

The controlled agent platform is suitable for a tenant-scoped pilot in local, test, or shadow
mode. It must not be represented as fully production-cleared until the three blocked items below
are completed with real Beo Art Studio data and infrastructure.

## Blocked production evidence

1. Run the migration and RLS/cross-tenant smoke suite against the target PostgreSQL cluster using
   the production application and migration roles.
2. Collect, redact, approve, and human-review at least 50 representative Beo Art Studio commission
   enquiry examples. The synthetic 50-case test corpus is load evidence, not customer evidence.
3. Run and approve a pinned evaluation report for the Beo workflow and record real baseline
   metrics before promotion beyond shadow mode.

These are deployment/data activities, not safe facts to infer from repository code.

## Security

| Control | Status | Evidence |
| --- | --- | --- |
| RLS declared for tenant-owned tables | Pass in migrations | Full metadata-to-migration control test and migration `0013` through `0026` |
| Cross-tenant controls | Pass in source tests | RLS policies, relationship triggers, tenant isolation suite |
| No production global credential fallback | Pass | Production WhatsApp fallback test and default-disabled setting |
| Tool permission enforcement | Pass | Registry checks tenant, workflow, role, constraints, and permission before execution |
| Connector secrets encrypted | Pass | Fernet storage test; connector columns store encrypted tokens |
| Audit records | Pass | Workflow, tool, approval, recovery, payment, deployment, and administration paths record actors |
| Live PostgreSQL enforcement | Blocked | Must be smoke-tested on the target database |

## Reliability

| Control | Status | Evidence |
| --- | --- | --- |
| Durable jobs | Pass | PostgreSQL job table, leasing, bounded retries, and worker |
| Idempotent external actions | Pass | Tenant-scoped keys and request hashes on jobs, tools, workflows, payments, and webhooks |
| Retry and dead letter | Pass | Shared recovery policy, scheduled retry state, dead-letter state, and recovery API/UI |
| Unknown external state reconciliation | Pass | Tool state classification and reconciliation records prevent blind replay |
| Webhook handling | Pass in source | Signature/replay checks and bounded database work; verify latency under production load |

## Agent quality and onboarding

| Control | Status | Evidence |
| --- | --- | --- |
| AI executions and workflow traces recorded | Pass | Versioned execution, step, context, cost, latency, and trace records |
| Original and edited outputs preserved | Pass | Approval and human-correction records retain both payloads and reasons |
| Dataset/evaluation/regression/deployment gate | Pass as platform capability | Dataset, result, threshold, report, proposal, approval, and rollback records |
| Automatic prompt mutation prohibited | Pass | Corrections create reviewed candidates/suggestions; no runtime prompt writer exists |
| Progressive onboarding and first-problem selection | Pass | Session stages, discovery answers, draft workflow specification, and explicit permissions |
| Test-before-activation and shadow mode | Pass | Deployment modes and Beo workflow default to shadow with external action suppressed |

## Beo Art Studio

| Control | Status | Evidence |
| --- | --- | --- |
| Commission enquiry workflow | Pass in code, not live deployment | Website/email/WhatsApp/manual triggers create a shadow workflow run |
| Human approval and safe pricing/promises | Pass | Official prices are authoritative; risk conditions create structured approval |
| Outcomes and baseline capability | Pass as platform capability | Outcome and workflow baseline models plus value dashboard |
| 50 reviewed customer examples | Blocked | No approved production dataset was supplied |
| Approved live evaluation and baseline | Blocked | Requires tenant data and accountable human approval |

## Product and build

The bounded Operator uses registered read tools and proposes controlled actions. Marketing
opportunities and experiments, the value dashboard, workflow traces, approval queue, and recovery
interface are present.

Run `powershell -ExecutionPolicy Bypass -File scripts/release_gate.ps1` from the repository root.
It checks Ruff, strict mypy, backend tests, offline migration upgrade/downgrade generation,
frontend production build/typecheck, and whitespace integrity.

## Production deployment checklist

1. Freeze and tag the reviewed revision; record image digests and owners.
2. Back up PostgreSQL and verify restore access.
3. Configure unique production secrets, Clerk, provider credentials, Paystack webhook, allowed
   origins, and worker processes; leave global credential fallback disabled.
4. Apply migrations through `20260726_0026`; confirm the Alembic head.
5. With the production application role, verify RLS denies cross-tenant reads and writes for every
   tenant table and verify relationship triggers reject cross-tenant references.
6. Deploy backend and workers together, then the frontend.
7. Test signed WhatsApp and Paystack webhooks, duplicate delivery, tool permission denial,
   approval/resume, dead-letter recovery, and unknown-state reconciliation.
8. Import and approve the 50-example Beo dataset; run the pinned evaluation and obtain a named
   deployment approval.
9. Record baseline metrics, activate shadow mode only, and monitor trace completeness, queue age,
   approval age, webhook latency, errors, cost, and customer outcomes.
10. Promote only after sustained reviewed performance; keep an approved rollback deployment.

## Migration and rollback

Deploy schema before application code. The forward path is Alembic head `20260726_0026`.
Application rollback should use the deployment record's pinned prior version while retaining the
new schema when it remains backward compatible. The verified schema rollback is
`20260726_0026:20260726_0025`, which removes payment webhook and transaction tables; export and
reconcile payment records first because that downgrade is data-destructive. Older downgrades must
be rehearsed separately on a restored backup. Never downgrade a live database merely to clear an
alert.

# BeoOS internal operating policies

## Customer data and retention

Collect only data required for the selected workflow. Tenant data, credentials, datasets,
operator conversations, logs, and outcomes remain tenant-scoped. Define retention periods by
record type and contract; preserve legally required payment, security, and audit records while
honouring valid deletion requests for other data. Redact private examples before dataset use.

## Dataset use

Private production records never become global or industry examples automatically. Dataset use
requires provenance, tenant ownership, privacy review, redaction where required, explicit approval,
and a stated evaluation purpose. Corrections are evidence, not permission to retrain a model.

## AI safety

AI may classify, extract, summarize, draft, and recommend within schemas. Deterministic code owns
identity, tenant routing, pricing calculation, permissions, idempotency, payment evidence, and
deployment gates. Humans approve high-risk, financial, legal, irreversible, sensitive, or public
actions. BeoOS does not expose hidden chain-of-thought or self-modify prompts and policies.

## Model providers

Approve providers through security and privacy review. Document data sent, retention controls,
region, subprocessors, model/version, and opt-out settings. Send the minimum relevant context and
do not enable provider training on customer data without explicit contractual authority.

## Tool approval

Every executable tool requires an owner, schema, risk level, minimum role, tenant permission,
timeout, retry/reconciliation policy, audit output, and disable procedure. External tools default
to approval-required. A connector credential alone does not grant workflow permission.

## Tenant isolation

Application queries include `business_id`; PostgreSQL RLS is defense in depth. Global templates
are read-only and contain no tenant data. Cross-tenant relationships are blocked with triggers and
tested. Global production credential fallback is prohibited.

## Incidents and public authority requests

Escalate security, privacy, availability, payment, and provider incidents to the designated owner.
Preserve evidence and communicate confirmed facts. Public-authority requests require identity and
legal-authority validation, scope minimization, counsel review where appropriate, and a disclosure
record. Do not disclose customer data based on an informal request.

## Change management

Workflow, model, prompt, policy, and permission changes require versioning, regression evaluation,
deployment approval, and rollback data. Emergency changes must be narrowly scoped, recorded, and
retrospectively reviewed. No team member may bypass the gate by editing production rows manually.

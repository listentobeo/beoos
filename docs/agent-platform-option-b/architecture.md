# Architecture

## Current communication pipeline

```text
Zoho/Gmail scheduler, website form, or WhatsApp webhook
  -> validate and identify tenant
  -> normalize contact, thread, and message
  -> deduplicate provider message/event
  -> deterministic noise rules
  -> structured LLM triage and draft
  -> persist EmailAnalysis and EmailDraft
  -> deterministic tenant policy evaluation
  -> safe email auto-acknowledgement or approval queue
  -> provider send
  -> EmailMessage and partial AuditLog
```

Website and WhatsApp intake currently perform AI work inside the request. Email scheduling and
follow-up/report scheduling are in-process tasks. These are migration targets for durable jobs.

## Target Option B flow

```text
external event
  -> validate, persist, deduplicate, enqueue
  -> WorkflowRun
  -> deterministic step
  -> AIExecution when judgment is required
  -> policy/validation step
  -> ToolCall proposal
  -> ApprovalRequest when required
  -> permission revalidation and idempotent execution
  -> result/reconciliation
  -> Outcome
  -> evaluation candidate, never automatic prompt mutation
```

The workflow runner is a bounded state-transition service, not a general planner. PostgreSQL is
the source of durable execution state.

## First reference workflow

`beo_art_commission_enquiry_v1` normalizes website form, Gmail, Zoho, WhatsApp, and manual
enquiries into the same structured input. Deterministic steps perform tenant routing,
deduplication, customer matching, approved price lookup, business-hours/timeline checks, policy
routing, and idempotency. The existing structured triage model is limited to classification,
extraction, ambiguity/missing-information analysis, urgency/risk inference, summary, and a
suggested reply.

The initial deployment mode is `shadow`: proposed CRM/follow-up work is recorded with
`execute: false`, and email auto-send is suppressed until a later evaluation-backed deployment
permits external actions. Mandatory risk categories create structured approval requests. Outcomes
are appended to the workflow run rather than inferred from conversation history.

## Controlled operator

The BeoOS Operator uses deterministic routing for obvious requests and may narrow that plan using
model-selected tools only from the bounded operator registry. Tenant membership and role checks
run before selection. A turn is limited to four read/propose tools, two loops, 30 seconds, and a
preflight cost budget. Tool results remain tenant-scoped; arbitrary tools and direct external
execution are unavailable.

Important answers return structured grounding references and distinguish database facts from
model inference, recommendations, and missing information. Operator conversations are persisted
per tenant for continuity but carry a database constraint marking them non-authoritative.
Starting an evaluated workflow or creating an approval proposal uses explicit validated endpoints;
neither path bypasses deployment mode, tool permission, or later human approval.

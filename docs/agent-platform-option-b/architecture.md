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


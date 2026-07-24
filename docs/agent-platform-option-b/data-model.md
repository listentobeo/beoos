# Data model

## Existing sources of truth

- `businesses` and `business_members`: tenant identity and access.
- `contacts`, `email_threads`, `email_messages`: communication history.
- `email_analyses`, `email_drafts`: AI output and proposed communication.
- `price_catalog_items`: approved pricing.
- `crm_leads`, `follow_up_tasks`: pipeline and scheduled work.
- `quote_templates`, `quotes`: deterministic commercial proposals.
- `marketing_metrics`: imported growth signals.
- `audit_logs`: partial operational audit.

## New bounded platform records

- workflow definitions, runs, and steps;
- AI executions;
- tool definitions, permissions, and calls;
- approval requests and human corrections;
- outcomes;
- durable jobs;
- typed/versioned profile, service, policy, and staff authority;
- onboarding sessions and responses;
- datasets, examples, evaluation runs/results, and deployment records;
- marketing opportunities/experiments;
- payment transactions.

Every tenant-owned row has a non-null `business_id`. Global template rows are immutable to
tenants and explicitly identified. Context and evaluation references must preserve provenance
instead of copying undocumented prompt text.

## Versioned business context

`business_profiles`, `business_services`, and `business_policies` are append-versioned. A new
version points to the record it supersedes; previous versions remain available for trace and
evaluation replay. `business_staff_authorities` adds approval, financial, channel, and escalation
limits without replacing Clerk membership.

Each context record carries source type/ID, authority, effective and expiry timestamps, approval
status, and approver. The context builder only promotes effective approved records to official
facts. Legacy `businesses` fields and `Business.settings.ai_policy` remain non-destructive fallback
inputs and are labelled temporary/unversioned until onboarding creates approved typed records.
Approved price-catalog rows remain the authoritative pricing source.

## Evaluation datasets

`datasets` and `dataset_examples` provide versioned, reusable evaluation inputs at global,
industry, or tenant scope. Global datasets are platform-managed and read-only to tenants.
Every example records its provenance, privacy classification, redaction state, and human-review
status so onboarding and production traces cannot silently become evaluation data.

`evaluation_runs` pin a workflow definition/version, dataset/version, model, prompt, policy, and
evaluator configuration. `evaluation_results` store one result per example with dimension-level
scores and structured evidence. Deterministic checks are recorded separately from AI grading and
run first; AI grading supplements those checks rather than replacing them. Tenant-integrity
triggers reject cross-business workflow, dataset, example, run, and source references.

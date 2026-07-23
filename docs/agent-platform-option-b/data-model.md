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


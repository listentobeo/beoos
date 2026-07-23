# Security model

## Tenant boundary

The application authenticates with Clerk and authorizes membership through `BusinessMember`.
Every tenant operation must also carry an explicit `business_id`. Request correlation IDs support
tracing but never authorize access.

Database RLS is defense in depth. The initial migration enables RLS only for its original tables.
The following later tenant-owned tables currently lack RLS and are Phase 1 blockers:

- `push_subscriptions`
- `crm_leads`
- `quotes`
- `follow_up_tasks`
- `quote_templates`
- `marketing_metrics`
- `whatsapp_connections`
- `whatsapp_signup_attempts`
- `whatsapp_webhook_events`
- `external_api_tokens`

New workflow, job, context, onboarding, evaluation, marketing-experiment, and payment tables must
receive RLS in the migration that creates them.

## Credential findings

`WhatsAppCloudService` currently falls back from tenant credentials to global
`WHATSAPP_ACCESS_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID`. Production multi-tenant execution must
fail closed instead. Any development fallback must require an explicit non-production flag.

Provider application credentials used to complete OAuth are platform credentials. Per-tenant
access and refresh tokens remain encrypted tenant records.

## External effects

All external effects require tenant validation, a tool permission, idempotency, an audit/trace
record, sanitized failures, and reconciliation when provider success is uncertain.


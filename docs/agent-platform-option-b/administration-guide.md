# BeoOS administration and recovery guide

## Daily checks

- Health endpoint and deployed revision.
- Durable jobs in `dead_letter` or `retry_scheduled`.
- Tool calls in failed or unknown state.
- Open reconciliations and approval timeouts.
- Paystack transactions pending beyond the expected settlement window.
- Workflow failure, correction, and rejection rates.
- Connector authentication and token expiry.

## Recovery procedure

1. Identify the tenant, workflow, step, tool call, idempotency key, and request hash.
2. Determine whether the provider definitely did not act, definitely acted, or is unknown.
3. For unknown state, query the provider or use its reconciliation endpoint before retry.
4. Retry only categories marked retryable and preserve the original idempotency key.
5. Record the resolution, provider reference, operator, and reason.
6. Confirm the workflow outcome and customer-facing status.

Never edit database status directly to make an alert disappear.

## Paystack

Configure `PAYSTACK_SECRET_KEY` and use:

`POST /api/v1/webhooks/paystack`

Paystack sends `x-paystack-signature`; BeoOS verifies the raw body before parsing it. A successful
event must match the stored reference, deposit amount in minor units, and currency. Use the
tenant payment reconciliation endpoint when a signed webhook is missing. Do not accept screenshots
or AI interpretation as payment confirmation.

## Deployment and rollback

Back up the database, apply migrations, deploy backend and worker together, deploy frontend, and
run smoke tests. Monitor errors, dead letters, approvals, provider webhooks, and payment pending
age. Roll back application code to the deployment’s recorded rollback version. Downgrade schema
only when the migration plan confirms no newer data will be lost.

## Incident response

For suspected cross-tenant access or secret exposure: stop affected external execution, preserve
logs, rotate credentials, identify tenants and records, notify the incident owner, assess legal
notification duties, remediate, test the boundary, and document timeline and lessons. Do not place
raw secrets or unnecessary personal data in tickets.

## Access administration

Use least privilege. Owners and administrators configure workflows; managers approve within
delegated authority; agents handle operational work; viewers are read-only. Review staff authority,
financial limits, connector access, and external API tokens regularly. Remove access promptly when
a staff member leaves.

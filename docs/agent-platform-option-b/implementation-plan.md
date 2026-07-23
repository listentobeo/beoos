# Implementation plan

## Ordered delivery

1. Establish the verified baseline and document current risks.
2. Close tenant-security gaps before adding workflow features.
3. Add tenant-scoped workflow, AI execution, tool, approval, correction, and outcome records.
4. Add PostgreSQL-backed durable jobs and move webhook AI work out of requests.
5. Centralize real executable tools and permissions.
6. Introduce typed, versioned business context without destructively replacing settings.
7. Add progressive onboarding and workflow discovery.
8. Deploy the Beo Art Studio enquiry workflow in shadow then approval-required mode.
9. Add trace, approval, correction, evaluation, deployment-gate, recovery, and value interfaces.
10. Upgrade marketing and the operator only after the underlying controls exist.

Each phase has its own commit and must pass backend tests, Ruff, frontend typecheck, frontend
production build, and relevant migration/tenant-isolation checks.

## Security gates

Agent features must not precede:

- complete RLS coverage for tenant-owned tables;
- removal of production global connector fallback;
- cross-tenant association tests;
- explicit service-role documentation;
- tenant and correlation context on relevant requests.

## Existing external effects

| Effect | Current entry point | Present control |
|---|---|---|
| Send email | email draft approval and safe auto-acknowledgement | policy plus admin approval for queued drafts |
| Send WhatsApp | WhatsApp draft approval | admin approval |
| Create payment link | quote payment-link endpoint | admin role |
| Accept quote | public-token endpoint | possession of token |
| Change CRM stage | CRM/quote endpoints | admin role |
| Schedule follow-ups | CRM endpoint | admin role |
| Marketing publication | not implemented | none required |
| MCP writes | not implemented; MCP is read-only | token scopes |
| Inbound webhooks | Meta and website endpoints | signature/form key and deduplication |
| Account connections | OAuth and Meta signup | admin role, signed/recorded state |

All external effects will gain an idempotency key, request hash, execution record, failure
classification, and reconciliation policy.


# BeoOS Option B

This directory is the implementation record for the approved workflow-first evolution of
BeoOS. The programme keeps FastAPI, Next.js, PostgreSQL/Supabase, Clerk, the existing tenant
model, and the current business modules.

The platform boundary is deliberate:

- deterministic services own permissions, prices, calculations, state transitions, and sends;
- AI performs bounded classification, extraction, drafting, and recommendation;
- humans approve risky or irreversible actions;
- workflow, AI, tool, approval, correction, and outcome records form the operational trace;
- deployment promotion depends on evaluation evidence.

The first reference deployment is the Beo Art Studio commission-enquiry workflow. This is not
a generic multi-agent framework and does not support automatic prompt rewriting or unrestricted
tool execution.

## Baseline

- Baseline commit: `2ac015bbf1d06e76054c149e8724b20a0be91e7a`
- Alembic head: `20260719_0012`
- Migration files: 12
- Backend tests: 14 passed
- Ruff: passed
- Frontend typecheck: passed
- Frontend production build: passed
- Backend strict mypy: 38 errors across 9 files

The mypy failures are an inherited baseline and must not be hidden. Critical execution paths
must be made type-clean before release.


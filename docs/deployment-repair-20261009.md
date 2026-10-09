# Railway deployment and business module repairs

The supplied Railway logs show pre-deploy migration `0012 -> 0013` failing with
`cannot insert multiple commands into a prepared statement`. The public API reported
revision `2ac015b` while GitHub main contained `c0a0ac7`. New frontend pages were therefore
calling endpoints absent from the running backend.

## Changes

- Split SQL batches in migrations `0013`, `0015`, and `0017` into individual asyncpg-compatible
  statements. Keep all RLS and relationship integrity controls.
- Remove the quotation token backfill's undeclared dependency on pgcrypto. It now uses two
  PostgreSQL random UUIDs for a unique, unpredictable token.
- Correct shared trigger guards for email records, workflow records, Operator messages, and
  payment events. Table-specific `NEW` fields must only be referenced inside that table's
  branch. In particular, outcome writes previously failed on nonexistent `affected_customer_id`.
- Add migration `20261009_0029` to replace those functions on installations already at `0028`.
  Its downgrade keeps the fixes because they are compatible with the previous schema.
- Add administrator recovery controls with audit reasons. Supported durable jobs can be retried
  without resetting their attempt history. Unknown external actions require reconciliation.
  Closed failures leave the recovery queue, and retries require an executable linked job.
- Preserve quotation records if catalogue, template, or CRM requests fail. Keep imported
  marketing signals visible if opportunity or experiment requests fail. Surface unavailable
  data with retry controls instead of reporting failed requests as empty business records.
- Explain missing workflow evidence on Business value and format currency code metrics.
- Match guest proposal viewing and acceptance in the frontend proxy to the backend's public
  endpoints. Other methods and private quotation operations still require authentication.
- Keep dashboards dynamic per authenticated request and return a useful 502 response if the
  API cannot be reached. Do not forward stale compression/length headers on decoded responses.
- Make the release gate check the actual latest rollback and run public quote route tests.

## Validation

Use Python 3.12, matching the Railway Dockerfile. The prior local Python 3.14 environment was
blocked by Windows Application Control when loading asyncpg and mypy; an isolated Python 3.12
environment works.

The source suite includes a prepared-statement regression check for every upgrade and downgrade.
The final run passed 173 backend tests, Ruff, strict mypy, two frontend route tests, frontend
type checking, the production build, and offline migration upgrade/downgrade generation.
The optional real PostgreSQL smoke test creates its own disposable database, migrates from base
to `0012`, seeds existing businesses, upgrades to head, rolls back/reapplies the latest revision,
and verifies existing businesses and all ORM columns.

It exercises quotation creation, public proposal acceptance, marketing import/summary, baseline
storage, measured workflow value, recovery retry/cancel/reconciliation, administrator checks,
and cross-business access denial. It also inserts records through shared triggers and verifies
that cross-tenant references remain rejected.

```powershell
# Set this only to a test PostgreSQL server where the test may create/drop its own database.
$env:BEOOS_TEST_POSTGRES_URL = "postgresql://postgres@127.0.0.1:55432/postgres"
cd backend
python -m pytest -q
python -m ruff check app tests
python -m mypy app
cd ../frontend
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
```

Frontend route tests use Node 22.6+ with TypeScript stripping. The PostgreSQL test is skipped
when `BEOOS_TEST_POSTGRES_URL` is unset. No production database credentials or provider tokens
are needed for these tests.

## Deployment verification

Railway applies the repository migrations in its existing pre-deploy command; Python migration
files do not need a separate manual upload. Verify a successful deployment at migration head
`20261009_0029`, then check `/api/v1/health` reports the newly pushed commit.

A successful source test is not evidence of a successful live deployment. Authenticated browser
checks with the actual business data and provider configuration are still needed after promotion.
The earlier release gate's customer dataset/evaluation requirements remain applicable.

# BeoOS MCP and Marketing Intelligence Audit

Audit date: 2026-07-29

## Current status

Before this change, MCP was partial: a public JSON-RPC route and seven executable read tools
existed, but MCP calls had no durable audit, rate limit, timeout, cross-tenant MCP tests, or
standards-correct notification response. Token creation accepted arbitrary scopes and token
use did not revalidate the creator's current membership.

After this change, the repository is ready for **staging read-only MCP testing**, subject to
deploying migration `20260729_0028` and setting production limits. Production enablement
remains a no-go until a staging token completes the client smoke test and the deployment
target is deliberately promoted.

## Endpoint and transport

- Endpoint: `POST https://beoos-production.up.railway.app/api/v1/mcp`
- Transport: stateless HTTPS JSON-RPC / Streamable HTTP-compatible POST
- Protocol: `2025-06-18`
- Authentication: `Authorization: Bearer` or `X-BeoOS-API-Key`
- Public reachability observed during audit: health returned HTTP 200; MCP returned HTTP 401
  without a token; GET and DELETE returned HTTP 405.
- The live health revision was `2ac015b`, not this workspace revision.

## Tenant isolation evidence

The enforced path is:

```text
raw credential
→ HMAC token hash lookup
→ active and unexpired ExternalAPIToken
→ current BusinessMember for token creator
→ token-owned business_id
→ per-tool scope
→ query containing that business_id
→ structured response
→ ExternalAPIRequestLog
```

No MCP input schema contains `business_id`. Connector credentials are not imported or read by
the MCP marketing service. The dedicated request log records business, token, method/tool,
correlation ID, status, latency, safe error fields, and timestamp. It is tenant-RLS protected.

MCP calls do not create workflow runs or ordinary `tool_calls`; they appear in the dedicated
external-access audit stream. This avoids inventing workflow/run IDs for independent client
reads.

## Connector truth table

| Connector | Classification | Evidence |
|---|---|---|
| Search Console | Manual import only | Configuration fields exist; no property OAuth verification, API pull, sync job, or freshness job exists. |
| Blogger | Manual import only | Blog ID and shared Google app fields exist; no Blogger API execution exists. |
| Microsoft Clarity | Manual import only | Project/token configuration exists; no Clarity API execution exists. |
| Website analytics | Manual import only | Website identity and import fields exist; no analytics connector exists. |

The UI now reports these as unverified/manual rather than connected.

## Marketing loop

Implemented internally:

```text
imported data
→ evidence and detection
→ opportunity proposal
→ human opportunity decision
→ experiment draft
→ human experiment approval
→ manual implementation record
→ comparison metrics
→ interpretation, confounders, reviewed lesson
```

There is no automatic external implementation. Official connector synchronization remains a
separate future deliverable.

## Deployment and GitHub risks

- GitHub `main` was public and unprotected during the audit.
- Remote `main` was `2ac015b`; local work was ahead.
- No GitHub Actions workflows were present.
- `.vercel/project.json` links the workspace to the `beoos` Vercel project.
- `railway.json` runs migrations and starts the API; the public Railway revision matched
  remote GitHub `main`, which is evidence of likely automatic deployment.
- Pushing local `main` may therefore alter both the frontend and API review environment.

Recommended release controls:

1. If remote revision `2ac015b` is the submitted Meta build, tag that exact commit
   `meta-review-2ac015b` before any push.
2. Protect `main` and require reviewed pull requests.
3. Develop on `develop` or a feature branch.
4. Disable automatic production promotion from ordinary pushes.
5. Promote an immutable tested commit manually.
6. Preserve the Meta review tag as the rollback target.

The WhatsApp standard Embedded Signup and Coexistence implementation was not modified by this
work.

## Go/no-go

- Push repository: **conditional go** only to a non-production branch until deployment
  automation is confirmed.
- Read-only MCP: **staging go**, production no-go until migration and real-client smoke test.
- Marketing proposal tools: **staging go** with separately issued `marketing:propose`.
- External marketing actions: **no-go**; none are implemented or exposed.

# BeoOS AI Operator and MCP Roadmap

BeoOS is moving from a manual dashboard into an AI-operated business command center.

The product has three interfaces:

```text
Dashboard UI
  Human workspace for inbox, CRM, quotes, prices, analytics, marketing, and settings.

BeoOS Operator
  In-app assistant that reads tenant context and recommends or prepares actions.

Remote MCP Server
  External AI interface for ChatGPT, Claude, Cursor, Codex, VS Code, and other MCP clients.
```

## Current foundation

The first operator layer is live as a safe read-and-plan assistant, and the quote layer now has an
AI draft endpoint that prepares structured quote data before a human creates the actual record.

It can inspect tenant-scoped context from:

- business profile and policy;
- inbox thread totals and recent threads;
- CRM lead pipeline;
- price catalogue / inventory sample;
- quote templates, recent quotes, and AI quote draft readiness;
- marketing data source availability;
- follow-up and approval signals.

At this stage the floating operator does not mutate data or send messages. Write actions are
returned as `needs_confirmation` suggestions. The dedicated quote studio can prepare draft quote
payloads, but a user must still click “Create quote from draft”.

Implemented tenant endpoints:

- `POST /api/v1/businesses/{business_id}/operator/chat`
- `POST /api/v1/businesses/{business_id}/quotes/ai/draft`
- `GET/PATCH /api/v1/businesses/{business_id}/marketing/connections`

## Shared tool registry direction

The same internal tool registry should power both the dashboard assistant and the future MCP server.

Read-only tools:

- `list_businesses`
- `get_business_profile`
- `list_inbox_threads`
- `get_thread`
- `list_crm_leads`
- `list_price_items`
- `list_quotes`
- `get_marketing_summary`
- `get_daily_report`

Confirmation-gated tools:

- `create_price_item`
- `update_price_item`
- `create_crm_lead`
- `update_lead_stage`
- `schedule_followup`
- `create_quote_draft`
- `send_email_reply`
- `send_whatsapp_message`
- `create_payment_link`

Every write tool must create an audit log and should require explicit confirmation from the user.

## Tenant and security rules

Every tool call must resolve:

```text
Clerk user
  -> business membership
  -> role permission
  -> tool permission
  -> audit log
  -> action
```

The MCP server must never expose raw database access. It should expose business capabilities only.

## Quote intelligence direction

The quote operator now starts to:

- read a client thread or CRM lead;
- pull relevant price catalogue items;
- apply a business-specific quote template;
- produce structured quote input data for review.

Next it should:

- accept uploaded images or files;
- generate a designed client proposal;
- prepare Paystack / Stripe payment links;
- keep Beo Art Studio quote design as one reusable tenant template;
- allow other businesses to define their own quote schema.

Example:

```text
"Create a quote for this church mural client using our premium Beo Art Studio template."
```

The operator should produce a draft quote, not send it automatically.

## Marketing intelligence direction

Marketing connectors should become tenant-owned integrations:

- Google Search Console for page/query performance;
- Blogger for content inventory and draft planning;
- Microsoft Clarity for behavior signals;
- website/manual imports as fallback.

The first live marketing intelligence output should be:

- content clusters;
- weak-page opportunities;
- query gaps;
- pages needing refresh;
- weekly action plan.

Publishing should remain approval-gated.

## MCP publication direction

Once the shared tool registry and OAuth security are stable, expose BeoOS as a remote MCP server.

Initial target registries:

1. Official MCP Registry
2. Smithery
3. Glama

Positioning:

> BeoOS is an AI-native business operating system for creative businesses and SMEs.

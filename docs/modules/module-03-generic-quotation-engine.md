# Module 3: Generic Quotation Engine

Module 3 adds tenant-scoped quotations to BeoOS. It is not a Beo Art Studio-only feature: the quotation system is generic, and each quote belongs to one business, one optional CRM lead, and one optional contact.

The first production template is the mural quotation template. Future templates can support any brick-and-mortar or service business, such as interior design, signage, cleaning, construction, training, catering, photography, or repairs.

## What this module does

- Stores quotes per business/tenant.
- Allows CRM leads to become draft quotations.
- Calculates mural project costs from dimensions, design, labor, materials, equipment, transport, risk, overhead, profit, and deposit terms.
- Produces structured proposal content for client-facing quote documents.
- Keeps internal calculation data separate from the customer proposal.
- Tracks quote lifecycle status: draft, needs approval, approved, sent, accepted, rejected, and expired.
- Adds a Quotations dashboard page and quote detail view.

## Architecture

```text
frontend/app/dashboard/quotes
  lists tenant quotes and opens quote detail pages

frontend/components/dashboard/create-quote-button.tsx
  creates a quote from a CRM lead

backend/app/api/quotes.py
  tenant-scoped quote API

backend/app/domain/quotes.py
  Pydantic quote contracts and mural input schema

backend/app/services/quote_engine.py
  reusable calculation engine with template dispatch

database/migrations/versions/20260711_0004_quotes.py
  quotes table, quote status enum, template type enum
```

## Tenant behavior

Every quote is scoped by `business_id`. A quote can be linked to:

- a CRM lead;
- a contact;
- both;
- neither, for manual walk-in or phone-call quotes later.

This means Beo Art Studio, AIHD Studio, and future businesses can all use the same quotation engine without mixing data.

## Mural template v1

The mural template calculates:

- wall area in square feet and square metres;
- design costs;
- labor rows;
- materials;
- equipment;
- transport;
- project management fee;
- overhead;
- risk allowance;
- profit;
- final total;
- 70% deposit requirement.

The defaults are practical Beo Art Studio mural defaults, but the engine accepts per-quote inputs so the same template can be edited per job later.

## Current workflow

1. A customer message enters BeoOS from Zoho, Gmail, WhatsApp, or website forms.
2. Module 2 turns that opportunity into a CRM lead.
3. In CRM, click **Create quote** on the lead.
4. BeoOS creates a draft quotation and links it to the lead/contact.
5. Open **Quotations** to inspect totals, deposit, proposal content, and calculation breakdown.

## Next upgrades

- Editable quotation forms in the dashboard.
- PDF proposal generation.
- Client approval/acceptance link.
- Deposit tracking.
- Quote email/WhatsApp sending.
- Template builder for other service businesses.
- AI-assisted scope generation from conversations and business policy.

## Required keys

No new external API key is required for Module 3.

Required existing services:

- Clerk, for authenticated users and tenant access;
- PostgreSQL/Supabase, for quote storage;
- OpenAI, only when future AI-assisted scope/proposal generation is enabled.

## Verification

```powershell
cd backend
.\.venv\Scripts\alembic.exe -c alembic.ini upgrade head
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m pytest

cd ..\frontend
npm.cmd run typecheck
```

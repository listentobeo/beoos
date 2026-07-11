# Module 2: CRM Lead Pipeline

Module 2 turns BeoOS from a unified communication inbox into a sales pipeline.

## What it does

- Adds tenant-scoped CRM leads.
- Links each lead to:
  - business;
  - contact;
  - source inbox thread;
  - source channel.
- Tracks sales stages:
  - new;
  - contacted;
  - qualified;
  - quote needed;
  - quoted;
  - deposit pending;
  - won;
  - lost.
- Stores service, budget, deadline, estimated value, probability, follow-up date, and notes.
- Adds CRM dashboard page:
  - pipeline cards by stage;
  - open pipeline count;
  - estimated open value;
  - follow-up count;
  - won/lost summary.
- Adds “Create CRM lead” action inside inbox thread pages.
- Prefills leads from AI analysis where available:
  - service;
  - budget;
  - deadline;
  - deal signal probability.

## Architecture

```text
Zoho / Gmail / WhatsApp / Forms
  -> unified inbox thread
  -> contact
  -> CRM lead
  -> quotation engine later
```

The CRM does not duplicate the inbox. It sits above it. A thread can become a lead, and the lead keeps a link back to the original conversation.

## Database

New table:

```text
crm_leads
```

Important constraints:

- `business_id + thread_id` is unique, so the same conversation does not create duplicate leads.
- stage and source use database enums.
- indexes exist for business/stage and business/updated_at.

## API

```text
GET    /api/v1/businesses/{business_id}/crm/leads
GET    /api/v1/businesses/{business_id}/crm/stats
POST   /api/v1/businesses/{business_id}/crm/leads
POST   /api/v1/businesses/{business_id}/crm/threads/{thread_id}/lead
PATCH  /api/v1/businesses/{business_id}/crm/leads/{lead_id}
```

## Dashboard

New page:

```text
/dashboard/crm
```

Inbox thread pages now include a CRM card for converting a conversation into a sales lead.

## What is not included yet

These belong to the next modules:

- Quote generation and PDF quotation documents.
- Deposit/payment tracking.
- Automated follow-up sequences.
- Client lifecycle management after a won deal.
- Forecast charts and advanced analytics.

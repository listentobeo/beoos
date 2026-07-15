# Module 3.7: Follow-up Scheduler and Approval Alerts

## Job

Module 3.7 keeps deals warm after they enter the CRM. It schedules follow-up steps for open leads, creates reply drafts when follow-ups are due, and alerts the business owner before anything is sent.

## What it does

- Schedules tenant-scoped follow-up sequences from CRM leads.
- Supports three cadences:
  - `standard`: 24 hours, 2 days, 7 days;
  - `hot`: 6 hours, 24 hours, 3 days;
  - `gentle`: 2 days, 7 days, 14 days.
- Creates pending `EmailDraft` records instead of auto-sending.
- Moves the related conversation to `needs_approval`.
- Sends browser push and Resend email alerts when a follow-up draft needs approval.
- Skips follow-ups when the lead is closed, the thread is missing, or the client has already replied.

## Tenant model

Every follow-up task belongs to one `business_id`. A lead in one tenant cannot schedule, view, or process follow-ups for another tenant.

## Why approval-gated

Follow-ups can affect client trust. BeoOS prepares the message, but the business owner approves before sending. This keeps the automation sharp without becoming reckless.

## Offline awareness

Active now:

- browser/device push notifications;
- email alerts through Resend.

Prepared for later:

- SMS via Termii, Africa's Talking, or Twilio;
- WhatsApp template alerts after Meta production approval.

## API

```http
POST /api/v1/businesses/{business_id}/crm/leads/{lead_id}/follow-ups
```

Body:

```json
{ "cadence": "standard" }
```

```http
GET /api/v1/businesses/{business_id}/crm/follow-ups
POST /api/v1/businesses/{business_id}/crm/follow-ups/{task_id}/cancel
```

## Deployment

No separate worker service is required in the current build. The scheduler starts inside the FastAPI API service and is controlled by:

```env
FOLLOW_UP_SCHEDULER_ENABLED=true
FOLLOW_UP_SCHEDULER_INTERVAL_SECONDS=60
FOLLOW_UP_SCHEDULER_BATCH_SIZE=10
```

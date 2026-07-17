# Daily business reports

BeoOS can send each business tenant a daily operating report from the data already inside the OS.

## What the report includes

- inbound messages received today;
- unread inbox count;
- WhatsApp message count;
- conversations waiting for approval;
- new CRM leads;
- hot open leads;
- quotes created and accepted;
- due follow-ups;
- pending AI drafts;
- open and accepted quote value;
- recent inbox activity.

## How it works

Each business stores its own report settings in `businesses.settings.daily_report`.

```json
{
  "enabled": true,
  "time": "18:00",
  "timezone": "Africa/Lagos",
  "email": "owner@example.com",
  "push_enabled": true,
  "last_sent_on": "2026-07-17"
}
```

The report can be tested manually from Business Settings. The backend scheduler checks enabled
businesses and sends once per local day after the configured time.

## API endpoints

```text
GET   /api/v1/businesses/{business_id}/reports/daily/settings
PATCH /api/v1/businesses/{business_id}/reports/daily/settings
GET   /api/v1/businesses/{business_id}/reports/daily/preview
POST  /api/v1/businesses/{business_id}/reports/daily/send-test
```

## Required platform setup

Email delivery uses Resend:

```env
RESEND_API_KEY=
ALERT_FROM_EMAIL=beoos@alerts.beoarts.com
```

Device alerts use the existing PWA push setup:

```env
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:support@beoos.com.ng
```

Scheduler controls:

```env
DAILY_REPORT_SCHEDULER_ENABLED=true
DAILY_REPORT_SCHEDULER_INTERVAL_SECONDS=300
DAILY_REPORT_SCHEDULER_BATCH_SIZE=25
```

## Production note

This is tenant-safe: the report always queries by `business_id` and uses the current business’
timezone, recipient email, and push subscriptions.

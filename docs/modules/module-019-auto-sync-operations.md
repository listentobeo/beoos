# Module 1.9: Auto Sync and Operations Layer

Module 1.9 makes BeoOS keep connected mailboxes fresh without needing a second Railway service.

## What it does

- Starts a mailbox auto-sync scheduler inside the existing FastAPI API service.
- Syncs connected Zoho and Gmail mailboxes automatically.
- Uses database leases so two running replicas do not sync the same mailbox at the same time.
- Keeps the old standalone worker entry point available for future scale-out.
- Exposes auto-sync status in mailbox status responses.
- Updates the dashboard inbox copy so operators can see whether auto-sync is active.

## Why this module exists

Before this module, BeoOS could sync manually and receive webhooks, but mailbox polling still depended on a separate worker process. Railway can run that later, but during early production the simpler architecture is:

```text
One Railway API service
  -> FastAPI routes
  -> OAuth callbacks
  -> WhatsApp webhooks
  -> Website form intake
  -> Push notifications
  -> Mailbox auto-sync loop
```

This avoids paying for, configuring, and monitoring a second Railway service until BeoOS actually needs dedicated background capacity.

## Environment variables

```env
MAILBOX_AUTO_SYNC_ENABLED=true
MAILBOX_AUTO_SYNC_INTERVAL_SECONDS=60
MAILBOX_AUTO_SYNC_BATCH_SIZE=10
MAILBOX_AUTO_SYNC_LEASE_MINUTES=5
```

## Production notes

- Keep one Railway API service for now.
- If traffic grows or sync work becomes heavy, create a separate worker service later using:

  ```powershell
  python -m app.worker
  ```

- If a separate worker is added later, set `MAILBOX_AUTO_SYNC_ENABLED=false` on the API service and `true` on the worker service.

# Module 1.7: Realtime Dashboard and Push Notifications

Module 1.7 makes BeoOS feel live while keeping the architecture simple and production-safe.

## Active in this version

- Dashboard auto-refreshes while the browser tab is visible.
- Inbox and message thread pages keep their server-rendered security model.
- Browser push subscriptions are stored per:

  - business;
  - Clerk user;
  - browser/device endpoint.

- New inbound messages can trigger Web Push notifications from:

  - Zoho/email sync;
  - website form intake;
  - WhatsApp Cloud API webhooks.

## Required backend environment variables

```env
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:admin@beoarts.com
```

## Frontend flow

Business Settings includes a notification card. A user enables notifications for the selected business on the current device. BeoOS registers the service worker, asks browser permission, and stores the encrypted push subscription on the backend.

## Delivery flow

```text
New message enters BeoOS
  -> saved to tenant inbox
  -> active push subscriptions for that business are loaded
  -> Web Push notification is sent
  -> clicking notification opens the inbox thread
```

## Remaining improvements

- Per-user notification preferences.
- Quiet hours.
- Native mobile app push.
- WebSocket/SSE live updates instead of polling refresh.
- Notification history/audit UI.

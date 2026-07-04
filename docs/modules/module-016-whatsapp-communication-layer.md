# Module 1.6: WhatsApp Communication Layer

Module 1.6 connects WhatsApp Cloud API to the tenant communication hub.

## What is active

- Meta webhook verification:

  ```text
  GET /api/v1/webhooks/whatsapp
  ```

- Meta inbound webhook receiver:

  ```text
  POST /api/v1/webhooks/whatsapp
  ```

- Per-business WhatsApp Cloud API settings in Business Settings:

  - enabled flag;
  - Meta phone number ID;
  - WhatsApp Business Account ID;
  - display phone number.

- Inbound WhatsApp text messages create:

  - a tenant-scoped mailbox connection with provider `whatsapp`;
  - a contact using the sender phone number;
  - a unified inbox thread;
  - an inbound message;
  - an AI/manual draft in the approval queue.

- Approved WhatsApp drafts send through Meta Cloud API.

## Current safety posture

WhatsApp replies are not auto-sent in this version. They are drafted and require human approval. This avoids accidental messages while templates, conversation-window rules, and business-specific response policies mature.

## Meta setup

Use this callback URL in Meta:

```text
https://beoos-production.up.railway.app/api/v1/webhooks/whatsapp
```

Subscribe to WhatsApp message events. Use the same `WHATSAPP_VERIFY_TOKEN` value in Railway and Meta.

## Required environment variables

```env
META_APP_SECRET=
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_GRAPH_BASE_URL=https://graph.facebook.com/v20.0
```

Optional global fallbacks:

```env
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_BUSINESS_ACCOUNT_ID=
```

For a multi-business setup, prefer saving the phone number ID per business in Business Settings.

## Remaining WhatsApp work

- Media download/storage for images, audio, and documents.
- Template-message management for business-initiated conversations.
- Conversation-window tracking.
- Delivery/read receipt handling.
- Push notifications to business users.
- Safer auto-send rules after real-world testing.

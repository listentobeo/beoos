# Module 1.5: Tenant Communication Hub

Module 1.5 upgrades BeoOS from a Zoho-only email assistant into a tenant-based communication intake layer.

## What this does for businesses

BeoOS becomes the front desk for a business:

```text
Website forms / Zoho Mail / future Gmail / future WhatsApp
        -> Unified BeoOS Inbox
        -> Contact + lead record
        -> Business AI policy
        -> AI draft/classification
        -> Approval queue / follow-up / notification
```

Each business has its own:

- inbox data;
- website form key;
- AI policy;
- brand instructions;
- pricing rules;
- channel rules;
- future provider connections.

## Active in this version

- Public website form endpoint per business:

  ```text
  POST /api/v1/forms/{business_slug}/lead
  ```

- Tenant form key stored in business settings.
- Website submissions create inbox threads and contacts.
- Website submissions create pending AI/manual drafts.
- OpenAI classification runs when `OPENAI_API_KEY` is configured.
- Resend can notify the business email when a website lead arrives.
- Business Settings shows endpoint, form key, and integration example.

## Why website forms are first

Website forms are the easiest reliable channel to activate before WhatsApp/Gmail because they do not require third-party OAuth approval or webhook verification. They also immediately turn website traffic into BeoOS leads.

## Next providers

### Gmail

Requires Google Cloud OAuth, Gmail API scopes, and a provider adapter.

Planned adapter:

```text
Gmail OAuth -> Gmail message sync/watch -> BeoOS inbox
```

### WhatsApp

Requires Meta Business, WhatsApp Cloud API, phone number, webhook verification, and message-template compliance.

Planned adapter:

```text
WhatsApp webhook -> BeoOS inbox -> AI policy -> reply/template/approval
```

### PWA/mobile push

Requires browser push subscriptions, VAPID keys, service worker registration, and a notification table. This should come after website forms because it needs more moving parts to be dependable.

## Website form payload

```json
{
  "form_key": "tenant-form-key-from-business-settings",
  "name": "Client name",
  "email": "client@example.com",
  "phone": "090...",
  "service": "Portrait",
  "budget": "NGN 250,000",
  "deadline": "Next week",
  "message": "I want a family portrait.",
  "source_url": "https://www.beoarts.com/order"
}
```

## Security notes

- Form submissions are scoped by business slug and secret form key.
- Form keys are per business.
- Submitted content is treated as untrusted user input.
- AI output is still checked by deterministic policy before any action.
- Website form submissions are not auto-sent until an outbound channel is connected.


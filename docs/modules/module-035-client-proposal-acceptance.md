# Module 3.5: Client Proposal Acceptance and Payment Links

Module 3.5 turns quotations into client-facing proposal links.

## What this module adds

- Public proposal links for quotes.
- Client-safe quote token instead of exposing internal IDs.
- Public proposal page at `/quotes/{publicToken}`.
- Client acceptance endpoint.
- Quote status update to `accepted`.
- Client viewed timestamp.
- Paystack-ready deposit payment link generation.
- Dashboard quote detail panel showing:
  - client proposal link;
  - Paystack deposit link when available;
  - payment-link creation action.

## Tenant behavior

Quotes remain scoped by `business_id` internally. Public quote links only expose the proposal content, pricing summary, and acceptance/payment action for that specific quote.

## Required keys

Paystack is optional until payment links are needed.

```env
PAYSTACK_SECRET_KEY=
PAYSTACK_PUBLIC_KEY=
```

## Replicate AI provider

BeoOS can now switch AI traffic from direct OpenAI to Replicate:

```env
AI_PROVIDER=replicate
REPLICATE_API_TOKEN=
REPLICATE_MODEL=openai/gpt-5.4
```

The shared AI service still has the original `OpenAIEmailService` class name for compatibility, but internally it routes to Replicate when `AI_PROVIDER=replicate`.

## Current limits

- PDF proposal export is not built yet.
- Paystack webhook verification is not built yet.
- Deposit-paid status is not automated yet.
- Proposal editing is still the next quotation upgrade.

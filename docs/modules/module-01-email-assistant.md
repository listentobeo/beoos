# Module 1: AI Email Assistant

## Business configuration

- Business: Beo Art Studio (first multi-business tenant)
- Inbox: `admin@beoarts.com` on Zoho Mail
- Owner: Benjamin Odeke
- Signature: `Benjamin Odeke` / `Beo Art Studio`
- WhatsApp handoff: `+234 907 542 4681`
- History import: previous 365 days from Inbox and Sent
- Calendar: not used

## Categories

Portrait, Mural, Live Painting, SFX, Art School, Existing Client, Corporate, General, Urgent, and Spam.

Sip & Paint is intentionally excluded. Art School enquiries remain in the email inbox.

## Channel policy

1. New individual deal opportunities may receive a WhatsApp handoff.
2. Existing clients remain on their current channel.
3. Corporate and professional clients remain on email.
4. Non-deal messages are never pushed to WhatsApp.
5. Urgent items appear in the platform and trigger a protected Resend alert.

## Automatic-send policy

The AI proposes a structured classification and acknowledgement. A deterministic policy engine is the final authority.

Auto-send is permitted only when all conditions are true:

- action is acknowledgement or qualified-deal handoff;
- model confidence is at least 0.90;
- no price, currency amount, complaint, refund, payment, discount, legal issue, or contract is involved;
- no unauthorized commitment appears in the response;
- channel-continuity rules pass;
- message arrived within the last 15 minutes.

Everything else enters **Needs Approval**.

## Pricing policy

Service pages are authoritative. Blog articles are educational estimates and never become quotations. Price catalogue records are versioned, approved, effective-dated, and linked to their source page. SFX remains custom-quote-only until an authoritative service-page price is approved.

## Data flow

```text
Zoho Mail -> sync worker -> PostgreSQL -> OpenAI structured triage
          -> deterministic policy -> auto acknowledgement OR approval queue
          -> Zoho reply -> audit log
```

OpenAI requests use `store=false`; the sender identifier is hashed before transmission.

## Dashboard

Unified Inbox, Needs Approval, Urgent, Existing Clients, WhatsApp Handoffs, Price Catalogue, Analytics, and Business Settings.

## Acceptance checks

- Duplicate Zoho messages are idempotent.
- Multiple workers cannot claim the same mailbox concurrently.
- Historical imports never send late replies.
- AI output must validate against the Pydantic schema.
- Human-approved sends and automated sends are auditable.
- Every query is scoped by `business_id` and Clerk membership.


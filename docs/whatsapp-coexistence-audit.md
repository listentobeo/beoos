# WhatsApp Business App Coexistence Audit

Date: 2026-07-18  
Project: BeoOS  
Scope: Meta WhatsApp Business App coexistence onboarding, tenant safety, webhook readiness, and production direction.

## Executive verdict

BeoOS is on the right track, but the current WhatsApp integration should still be treated as a Cloud API / Embedded Signup foundation, not a fully proven WhatsApp Business App coexistence implementation.

The app already has:

- Meta webhook verification and inbound webhook receiver;
- per-business WhatsApp settings;
- Meta Embedded Signup launch from the dashboard;
- backend token exchange;
- encrypted tenant token storage;
- inbound WhatsApp-to-inbox routing;
- AI draft creation for WhatsApp messages;
- approval-based outbound WhatsApp replies.

The remaining risk is not whether BeoOS can receive WhatsApp messages. It can. The risk is whether every tenant can connect an existing WhatsApp Business App number while keeping that number active on their phone, with safe reconnection, diagnostics, history sync, and Meta review evidence.

That coexistence path needs to be implemented and tracked as its own onboarding mode.

## Current stack

- Frontend: Next.js App Router, TypeScript, Tailwind, Clerk.
- Backend: FastAPI, async SQLAlchemy, PostgreSQL/Supabase.
- Auth: Clerk JWTs checked by the backend.
- Deployment: Vercel frontend, Railway backend.
- Main tenant model: `Business` + `BusinessMember`.
- Main inbox models: `MailboxConnection`, `Contact`, `EmailThread`, `EmailMessage`, `EmailAnalysis`, `EmailDraft`.

## Current WhatsApp files

### Frontend

- `frontend/components/dashboard/whatsapp-settings-form.tsx`
  - Loads the Facebook SDK.
  - Opens Meta login / Embedded Signup.
  - Sends returned code/token and signup payload to backend.
  - Lets an admin manually save phone number ID, WABA ID, and display number.

- `frontend/app/dashboard/settings/page.tsx`
  - Renders the WhatsApp settings card inside Business Settings.

### Backend

- `backend/app/api/businesses.py`
  - `GET /api/v1/businesses/{business_id}/whatsapp/embedded-config`
  - `POST /api/v1/businesses/{business_id}/whatsapp/embedded-signup`
  - `PATCH /api/v1/businesses/{business_id}/whatsapp`
  - Exchanges Meta authorization code or SDK token server-side.
  - Attempts to resolve WABA and phone number assets.
  - Encrypts the tenant access token.

- `backend/app/api/whatsapp.py`
  - `GET /api/v1/webhooks/whatsapp`
  - `POST /api/v1/webhooks/whatsapp`
  - Verifies Meta webhook signatures when `META_APP_SECRET` is configured.
  - Imports inbound WhatsApp messages into BeoOS inbox.
  - Creates tenant contacts, threads, messages, AI analysis, and pending drafts.

- `backend/app/services/whatsapp.py`
  - Sends approved outbound WhatsApp text messages through Cloud API.

- `backend/app/domain/business.py`
  - Defines `BusinessWhatsAppSettings`.
  - Currently keeps WhatsApp integration state inside `Business.settings["whatsapp"]`.

- `backend/app/core/config.py`
  - Existing environment settings:
    - `META_APP_SECRET`
    - `META_APP_ID`
    - `META_WHATSAPP_CONFIG_ID`
    - `WHATSAPP_VERIFY_TOKEN`
    - `WHATSAPP_ACCESS_TOKEN`
    - `WHATSAPP_PHONE_NUMBER_ID`
    - `WHATSAPP_BUSINESS_ACCOUNT_ID`
    - `WHATSAPP_GRAPH_BASE_URL`

## Existing flow

Current dashboard flow:

```text
Business Settings
  -> Connect with Meta
  -> frontend loads Facebook SDK
  -> FB.login with config_id
  -> frontend listens for WA_EMBEDDED_SIGNUP message
  -> frontend sends code/access token + WABA/phone identifiers to backend
  -> backend exchanges code/token
  -> backend discovers WABA and phone number
  -> backend stores encrypted access token in business settings
  -> WhatsApp webhook routes messages by phone_number_id/display number
```

This is a strong base.

One good sign: the frontend is already passing:

```ts
featureType: "whatsapp_business_app_onboarding"
sessionInfoVersion: "3"
```

That suggests the UI is attempting the coexistence-style Embedded Signup flow. However, BeoOS still uses only one `META_WHATSAPP_CONFIG_ID`, and the backend does not yet persist the signup mode, state, attempt, provider eligibility, or connection lifecycle separately. That makes it difficult to prove whether a tenant completed true coexistence onboarding or fell back into a normal Cloud API path.

## Why the user sees “This number is already in use”

Most likely cause:

The Meta setup path being used is still behaving like a dedicated Cloud API number registration/migration flow, or the selected Meta configuration is not eligible/configured for WhatsApp Business App coexistence.

In normal Cloud API onboarding, a number already active in WhatsApp or WhatsApp Business App can trigger “number already in use” because Meta expects that number to be migrated/deregistered before Cloud API ownership. That is exactly what BeoOS does not want for small businesses.

For coexistence, the user should not be told to remove WhatsApp Business from the phone. The product path should explicitly say:

> Keep WhatsApp on my phone.

And the app should launch only the Meta configuration intended for WhatsApp Business App onboarding/coexistence.

Other possible causes:

- The phone number is ordinary WhatsApp, not WhatsApp Business App.
- The WABA/phone is already controlled by another provider or technology partner.
- The Meta Business Portfolio user does not have admin access.
- App review/advanced access/business verification is incomplete.
- The Meta configuration ID is for the wrong onboarding variation.
- The app is in test/live mode mismatch or using wrong production domains.

Manual verification is still required in Meta Dashboard because BeoOS cannot infer all configuration eligibility from the repository.

## Current gaps versus production coexistence

### 1. No separate connection mode

Current value:

```py
connected_via = "manual" | "embedded_signup"
```

Needed:

```ts
connection_mode = "coexistence" | "cloud_api_only" | "unknown"
connection_status = "not_connected" | "signup_started" | "authorization_received" | "connecting" | "connected" | "action_required" | "disconnected" | "failed"
```

Why this matters: BeoOS must distinguish “tenant kept WhatsApp on phone” from “tenant connected a dedicated API number.”

### 2. No signup-attempt table

Current flow passes signup data directly from browser to backend.

Needed:

- create signup attempt before launching Meta;
- store tenant ID, user ID, mode, state, created time, expires time;
- validate state in callback/finalize;
- persist sanitized Meta errors;
- make retries idempotent.

### 3. WhatsApp credentials live inside `Business.settings`

This works, but production SaaS needs a dedicated integration record.

Needed table equivalent:

```ts
{
  businessId: string;
  metaBusinessId?: string;
  wabaId: string;
  phoneNumberId: string;
  displayPhoneNumber?: string;
  connectionMode: "coexistence" | "cloud_api_only" | "unknown";
  connectionStatus: string;
  accessTokenEncrypted: string;
  tokenExpiresAt?: Date;
  connectedByUserId: string;
  connectedAt?: Date;
  lastWebhookAt?: Date;
  lastHistorySyncAt?: Date;
  lastErrorCode?: string;
  lastErrorMessage?: string;
  metadata?: Json;
}
```

### 4. Webhook processing handles inbound messages, but not the full coexistence event set

Current support:

- webhook verification;
- signature verification;
- inbound text/media placeholder;
- tenant routing by phone number ID/display number;
- duplicate detection by provider message ID;
- AI draft creation;
- push/approval notification hooks.

Needed for coexistence:

- delivery/read/failure statuses;
- business-app/human message echoes where Meta provides them;
- chat-history synchronization events;
- account update events;
- disconnection/reconnection signals;
- source ownership: `customer`, `business_app`, `beoos_agent`, `beoos_ai`, `unknown`;
- pause AI if a human replies from the WhatsApp Business App;
- raw event storage with retention limits;
- queue expensive processing outside the webhook request.

### 5. No WhatsApp diagnostics page

Needed for tenant admins/support:

- connection mode;
- connection status;
- display number;
- masked WABA ID;
- masked phone number ID;
- webhook subscription status;
- last webhook received;
- last message received/sent;
- history sync state;
- token health;
- latest sanitized Meta error;
- reconnect/disconnect actions;
- “Run connection test.”

### 6. One config ID is not enough

Current env:

```env
META_WHATSAPP_CONFIG_ID=
```

Recommended:

```env
META_WHATSAPP_COEXISTENCE_CONFIG_ID=
META_WHATSAPP_CLOUD_CONFIG_ID=
WHATSAPP_COEXISTENCE_ENABLED=true
```

Keep the existing `META_WHATSAPP_CONFIG_ID` as a temporary fallback only.

## Proposed implementation plan

### Phase 1 — Audit-safe configuration split

- Add typed settings for coexistence and Cloud API-only modes.
- Update docs/API_KEYS.md.
- Update frontend card to show two paths:
  - “Keep WhatsApp on my phone” — recommended.
  - “Use a dedicated API number.”
- Keep current path working as fallback.

### Phase 2 — Database hardening

Add models/migrations:

- `whatsapp_connections`
- `whatsapp_signup_attempts`
- `whatsapp_webhook_events`

Add uniqueness constraints:

- one active connection per business;
- one active connection per phone number ID;
- one active connection per WABA/phone pair.

### Phase 3 — Secure signup lifecycle

- Backend creates signed signup attempt.
- Frontend launches Meta with selected mode.
- Backend finalizes only if state/user/business match.
- Store lifecycle status and sanitized errors.
- Map “number already in use” to a clear coexistence-specific explanation.

### Phase 4 — Webhook coexistence readiness

- Route by WABA ID and phone number ID.
- Store raw sanitized event metadata.
- Deduplicate events.
- Track `last_webhook_at`.
- Track message source.
- Detect human/business-app replies and pause AI drafts.

### Phase 5 — Diagnostics and reconnect

- Add admin diagnostics panel.
- Add reconnect/disconnect.
- Add run connection test.
- Add setup check results.

### Phase 6 — Tests

Mock Meta API calls and test:

- signup state validation;
- tenant isolation;
- duplicate callback handling;
- WABA subscription;
- webhook signature validation;
- event deduplication;
- message routing;
- human reply pause;
- error mapping;
- token encryption.

## Manual Meta Dashboard checklist

Manual verification required in Meta Dashboard:

- App is in the correct environment/mode for production testing.
- `beoos.com.ng` and `www.beoos.com.ng` are configured where Meta requires domains.
- OAuth redirect URL points to the exact frontend/backend route used by BeoOS.
- Webhook callback:

```text
https://beoos-production.up.railway.app/api/v1/webhooks/whatsapp
```

- Webhook verify token matches Railway `WHATSAPP_VERIFY_TOKEN`.
- WhatsApp product/use case is added.
- Required permissions are requested and tested.
- Embedded Signup configuration is the one intended for WhatsApp Business App onboarding/coexistence.
- Business verification / app review / access tier requirements are completed where Meta requires them.

Do not claim production coexistence works until a real eligible WhatsApp Business App number has completed this exact flow and BeoOS receives/sends test messages successfully.

## Immediate recommendation

Do not delete the current WhatsApp implementation. It is valuable and already proves the core pipeline.

Next build should be:

1. split the frontend into two WhatsApp connection choices;
2. add proper `connection_mode` and `connection_status`;
3. add signup-attempt tracking;
4. add a diagnostics panel;
5. keep current Cloud API connection alive as fallback.

That gives BeoOS a clean path through Meta review without risking the existing inbox/AI/CRM/quote system.


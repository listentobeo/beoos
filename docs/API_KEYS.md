# BeoOS API keys and external setup

This file lists the platform keys needed for the active BeoOS modules.

## Required now

### Supabase / PostgreSQL

Used for all BeoOS tenant data.

```env
DATABASE_URL=postgresql+asyncpg://...
```

### Clerk

Used for dashboard authentication and user identity.

```env
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
CLERK_SECRET_KEY=
CLERK_ISSUER=
CLERK_JWKS_URL=
```

### OpenAI

Used for AI classification, drafting, lead extraction, and policy-aware replies.

```env
OPENAI_API_KEY=
OPENAI_MODEL=
```

### Replicate

Alternative AI provider for testing and lower-cost internal automation. Set this when you want
BeoOS to use Replicate instead of direct OpenAI calls.

```env
AI_PROVIDER=replicate
REPLICATE_API_TOKEN=
REPLICATE_MODEL=openai/gpt-5.4
REPLICATE_TIMEOUT_SECONDS=90
```

Keep `AI_PROVIDER=openai` if you want to use direct OpenAI API keys instead.

### Secret encryption key

Used to encrypt OAuth tokens.

```env
SECRET_ENCRYPTION_KEY=
```

Generate with:

```powershell
cd backend
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Paystack

Used for proposal deposit payment links.

```env
PAYSTACK_SECRET_KEY=
PAYSTACK_PUBLIC_KEY=
```

## Active provider: Zoho Mail

Used for Beo Art Studio email sync.

```env
ZOHO_CLIENT_ID=
ZOHO_CLIENT_SECRET=
ZOHO_ACCOUNTS_BASE_URL=https://accounts.zoho.com
ZOHO_MAIL_BASE_URL=https://mail.zoho.com
```

Zoho callback:

```text
BACKEND_URL/api/v1/integrations/zoho/callback
```

Production example:

```text
https://beoos-production.up.railway.app/api/v1/integrations/zoho/callback
```

## Active in Module 1.9: Mailbox auto-sync

Used to pull new Zoho/Gmail messages automatically from the existing API service.

```env
MAILBOX_AUTO_SYNC_ENABLED=true
MAILBOX_AUTO_SYNC_INTERVAL_SECONDS=60
MAILBOX_AUTO_SYNC_BATCH_SIZE=10
MAILBOX_AUTO_SYNC_LEASE_MINUTES=5
```

Keep this enabled on the Railway API service while BeoOS runs as a single backend service. If you later create a separate worker service, disable it on the API service and enable it on the worker.

## Active in Module 3.7: Follow-up scheduler and approval alerts

Used to create approval-gated follow-up drafts for CRM leads and notify the business when a message needs approval.

```env
FOLLOW_UP_SCHEDULER_ENABLED=true
FOLLOW_UP_SCHEDULER_INTERVAL_SECONDS=60
FOLLOW_UP_SCHEDULER_BATCH_SIZE=10
```

No extra Railway service is required for the current build. The scheduler runs inside the existing API service.

## Active alerts: Resend

Used for urgent, website-lead, and needs-approval email alerts.

```env
RESEND_API_KEY=
ALERT_FROM_EMAIL=beoos@alerts.beoarts.com
```

## Optional future: SMS/text alerts

SMS requires a paid SMS gateway. BeoOS has configuration placeholders, but SMS delivery is not active until a provider integration is selected and implemented.

```env
SMS_PROVIDER=
SMS_API_KEY=
SMS_FROM=
```

Good provider options:

- Termii for Nigeria-focused SMS;
- Africa's Talking for wider African coverage;
- Twilio for global coverage;
- WhatsApp message templates after Meta production approval.

## Active website form intake

No third-party API key is needed.

Each business gets a tenant form key in Business Settings. The website posts to:

```text
NEXT_PUBLIC_API_URL/forms/{business_slug}/lead
```

Accepted form-key locations:

- JSON/body field: `form_key`;
- normal HTML hidden field: `<input type="hidden" name="form_key" value="..." />`;
- query string: `?form_key=...` or `?key=...`;
- server-side header: `X-BeoOS-Form-Key: ...`.

Accepted customer fields include common website/form-builder names:

- email: `email`, `_replyto`, `reply_to`, `client_email`;
- name: `name`, `full_name`, `client_name`;
- phone: `phone`, `whatsapp`, `mobile`;
- service: `service`, `subject`, `project_type`, `product`;
- message: `message`, `details`, `description`, `project_details`.

FormSubmit emails that arrive through a connected Zoho/Gmail mailbox are still supported. BeoOS extracts the real customer email from the form body and replies to that customer, not to `submissions@formsubmit.co`.

If the form is submitted directly from a browser on the business website, add that website to backend CORS:

```env
CORS_ORIGINS=https://beoos.vercel.app,https://www.beoarts.com,https://beoarts.com
```

## Active in Module 1.8: Gmail / Google Workspace

Used for Google mailbox OAuth, manual sync, and Gmail replies from BeoOS.

```env
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_ACCOUNTS_BASE_URL=https://accounts.google.com
GOOGLE_TOKEN_URL=https://oauth2.googleapis.com/token
GOOGLE_USERINFO_URL=https://openidconnect.googleapis.com/v1/userinfo
GOOGLE_GMAIL_BASE_URL=https://gmail.googleapis.com
```

Google callback:

```text
BACKEND_URL/api/v1/integrations/google/callback
```

Production example:

```text
https://beoos-production.up.railway.app/api/v1/integrations/google/callback
```

Google Cloud setup required:

- Google Cloud project;
- OAuth consent screen;
- Gmail API enabled;
- authorized redirect URI above;
- Gmail scopes for read and send.

Scopes used:

```text
openid
email
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.send
```

Near-real-time Gmail push/watch will be a later worker upgrade and may use:

```env
GOOGLE_PUBSUB_TOPIC=
```

## Active in Module 1.6: WhatsApp Cloud API

Used for inbound WhatsApp messages and approval-based replies.

```env
META_APP_SECRET=
META_APP_ID=
META_WHATSAPP_CONFIG_ID=
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_BUSINESS_ACCOUNT_ID=
WHATSAPP_GRAPH_BASE_URL=https://graph.facebook.com/v20.0
```

Meta setup required:

- Meta Business account;
- WhatsApp Business Account;
- connected phone number;
- webhook callback URL:

  ```text
  BACKEND_URL/api/v1/webhooks/whatsapp
  ```

- webhook verify token;
- per-business phone number ID saved in Business Settings;
- message templates for later business-initiated conversations.

Module 1.6 receives WhatsApp text messages and queues AI/manual replies for approval. Media, templates, delivery receipts, and automatic sends remain planned improvements.

## Active in Module 1.6.5: WhatsApp Embedded Signup

Used for the SaaS model where each customer connects their own WhatsApp Business Account
and phone number to a specific BeoOS business/tenant.

Flow:

```text
Business Settings
-> Connect with Meta
-> customer logs into Meta
-> Meta returns WABA / phone number / code
-> backend exchanges code for token
-> encrypted token + phone_number_id are stored under that BeoOS business only
-> WhatsApp webhooks route by phone_number_id
```

Meta setup required:

- app has WhatsApp product added;
- WhatsApp Embedded Signup configuration created in Meta;
- `META_APP_ID`, `META_APP_SECRET`, and `META_WHATSAPP_CONFIG_ID` set on Railway;
- the frontend reads the public Meta app/config values from the authenticated Railway API, so
  do not maintain a separate Vercel Meta app/config unless the code is intentionally changed;
- app domains include the BeoOS frontend domain;
- Facebook Login for Business client OAuth settings include the BeoOS frontend domain and the exact
  valid OAuth redirect URI used by the dashboard:

  ```text
  https://beoos.vercel.app/dashboard/settings
  ```

  If you use a different production frontend domain, add that same `/dashboard/settings` URL too.
- privacy policy, terms, and data deletion URLs are filled in before production review.

Manual WhatsApp setup still works for internal tenants. Embedded Signup is the recommended
path for external SaaS tenants because each tenant owns and authorizes their own WABA/number.

## Active in Module 1.7: PWA/mobile push

Used for browser/device alerts when new inbox messages arrive.

```env
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:support@beoos.com.ng
```

Push setup required:

- frontend service worker;
- browser permission prompt;
- subscription storage per user/device;
- backend Web Push sender;
- notification preferences per business/user.

Generate VAPID keys with:

```powershell
cd backend
.\.venv\Scripts\python.exe -m py_vapid --gen --json
```

Then add the public/private keys to both Railway backend services. The browser only receives the public key from the authenticated API.

## Planned next: Search Console / brand intelligence

Needed later:

```env
GOOGLE_SEARCH_CONSOLE_CLIENT_ID=
GOOGLE_SEARCH_CONSOLE_CLIENT_SECRET=
```

Used for:

- verified site performance;
- top queries;
- top landing pages;
- content opportunities;
- brand bible evidence.

# BeoOS API keys and external setup

This file lists the platform keys needed for Module 1 and Module 1.5.

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

## Active alerts: Resend

Used for urgent and website-lead email alerts.

```env
RESEND_API_KEY=
ALERT_FROM_EMAIL=beoos@alerts.beoarts.com
```

## Active website form intake

No third-party API key is needed.

Each business gets a tenant form key in Business Settings. The website posts to:

```text
NEXT_PUBLIC_API_URL/forms/{business_slug}/lead
```

If the form is submitted directly from a browser on the business website, add that website to backend CORS:

```env
CORS_ORIGINS=https://beoos.vercel.app,https://www.beoarts.com,https://beoarts.com
```

## Planned next: Gmail

Needed later:

```env
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_PUBSUB_TOPIC=
```

Google setup required:

- Google Cloud project;
- OAuth consent screen;
- Gmail API enabled;
- Gmail scopes approved;
- Pub/Sub topic for push/watch if using near-real-time sync.

## Active in Module 1.6: WhatsApp Cloud API

Used for inbound WhatsApp messages and approval-based replies.

```env
META_APP_SECRET=
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

## Planned next: PWA/mobile push

Needed later:

```env
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:admin@beoarts.com
```

Push setup required:

- frontend service worker;
- browser permission prompt;
- subscription storage per user/device;
- backend Web Push sender;
- notification preferences per business/user.

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

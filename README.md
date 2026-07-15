# BeoOS

BeoOS is the multi-business operating system for Beo companies. Module 1 implements the production foundation and the Beo Art Studio AI Email Assistant. Module 1.5 adds tenant-scoped website form intake so website enquiries can enter the same BeoOS inbox and AI policy pipeline. Module 1.6 adds WhatsApp Cloud API intake and approval-based WhatsApp replies. Module 1.6.5 adds WhatsApp Embedded Signup so SaaS tenants can connect their own Meta WhatsApp Business Account and phone number. Module 1.7 adds realtime dashboard refresh and browser push. Module 1.8 adds Gmail / Google Workspace as a second email provider. Module 1.9 adds automatic mailbox sync inside the existing API service. Module 2 adds the tenant CRM lead pipeline. Module 3 adds the generic quotation engine with the first mural quote template. Module 3.5 adds public proposal acceptance and Paystack-ready deposit links. Module 3.6 adds AI lead scoring and editable quote basics. Module 3.7 adds approval-gated follow-up scheduling and approval alerts. Module 3.8 adds tenant quote templates and flexible line-item quotes. Module 4.1 adds internal analytics and business intelligence across inbox, CRM, quotes, approvals, and follow-ups.

## Structure

```text
frontend/                  Next.js 15, TypeScript, Tailwind, shadcn/ui, Clerk
backend/app/api/           FastAPI routes
backend/app/domain/        Typed business contracts
backend/app/services/      Zoho, Gmail, OpenAI, policy, alert, and sync services
backend/app/infrastructure SQLAlchemy database layer
backend/prompts/           Versioned AI prompts
database/migrations/       PostgreSQL/Alembic migrations
docs/modules/              Approved module specifications
```

## Active modules

- [Module 1: AI Email Assistant](docs/modules/module-01-email-assistant.md)
- [Module 1.5: Tenant Communication Hub](docs/modules/module-015-tenant-communication-hub.md)
- [Module 1.6: WhatsApp Communication Layer](docs/modules/module-016-whatsapp-communication-layer.md)
- [Module 1.7: Realtime Dashboard and Push Notifications](docs/modules/module-017-realtime-notifications.md)
- [Module 1.8: Gmail / Google Workspace Connector](docs/modules/module-018-gmail-connector.md)
- [Module 1.9: Auto Sync and Operations Layer](docs/modules/module-019-auto-sync-operations.md)
- [Module 2: CRM Lead Pipeline](docs/modules/module-02-crm-lead-pipeline.md)
- [Module 3: Generic Quotation Engine](docs/modules/module-03-generic-quotation-engine.md)
- [Module 3.5: Client Proposal Acceptance and Payment Links](docs/modules/module-035-client-proposal-acceptance.md)
- [Module 3.6: AI Lead Scoring and Editable Quotes](docs/modules/module-036-lead-scoring-and-editable-quotes.md)
- [Module 3.7: Follow-up Scheduler and Approval Alerts](docs/modules/module-037-follow-up-scheduler.md)
- [Module 3.8: Quote Template Designer and Flexible Line Items](docs/modules/module-038-quote-template-designer.md)
- [Module 4.1: Internal Analytics and Business Intelligence](docs/modules/module-041-internal-analytics.md)
- [API keys and external setup](docs/API_KEYS.md)

## Local setup

1. Copy `.env.example` to `.env` and fill the secrets.
2. Generate the token-encryption key:

   ```powershell
   backend\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

3. Install and run the backend:

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
   .\.venv\Scripts\alembic.exe -c alembic.ini upgrade head
   .\.venv\Scripts\python.exe -m app.seed
   .\.venv\Scripts\uvicorn.exe app.main:app --reload
   ```

4. Install and run the frontend:

   ```powershell
   cd frontend
   npm.cmd install
   npm.cmd run dev
   ```

## External configuration

- **Clerk:** add the frontend URLs, then set the publishable key, secret key, issuer, and JWKS URL.
- **Zoho:** register a server OAuth client. Callback: `BACKEND_URL/api/v1/integrations/zoho/callback`. Use the Zoho accounts/mail base domains matching the mailbox data centre.
- **Gmail / Google Workspace:** enable Gmail API in Google Cloud, configure OAuth, and add callback `BACKEND_URL/api/v1/integrations/google/callback`.
- **AI provider:** set `AI_PROVIDER=openai` with `OPENAI_API_KEY`, or `AI_PROVIDER=replicate` with `REPLICATE_API_TOKEN`.
- **Resend:** verify the alert-sending domain and set `RESEND_API_KEY`.
- **Website forms:** Business Settings shows each tenant's endpoint and form key. No external API key is required.
- **WhatsApp Cloud API:** configure Meta webhook credentials globally, then either save a tenant's phone number ID manually or let the tenant connect their own WhatsApp Business Account through Embedded Signup in Business Settings.
- **Push notifications:** generate VAPID keys, set them on Railway, then enable browser notifications per business/device in Business Settings.
- **Mailbox auto-sync:** enabled by default in the API service. Tune with `MAILBOX_AUTO_SYNC_*` variables.
- **Follow-up scheduler:** enabled by default in the API service. Tune with `FOLLOW_UP_SCHEDULER_*` variables.
- **Paystack:** set `PAYSTACK_SECRET_KEY` when you want BeoOS to generate deposit payment links from proposals.
- **Supabase:** follow [SUPABASE_SETUP.md](SUPABASE_SETUP.md).

## Deployment

Deploy `frontend/` to Vercel. Deploy `backend/` to Railway as the API service:

- API service: repository root, config path `/railway.json`

The API configuration runs `alembic -c alembic.ini upgrade head` as its pre-deploy command. In Vercel Project Settings, set the Root Directory to `frontend`; do not deploy the FastAPI backend on Vercel.

A separate Railway worker service is optional later for heavier background jobs such as high-volume sync, retries, and daily reports. Manual sync, automatic mailbox sync, OAuth callbacks, WhatsApp webhooks, website forms, and push notifications work from the API service.

## Verification

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m mypy app

cd ..\frontend
npm.cmd run typecheck
npm.cmd run build
npm.cmd audit --omit=dev
```

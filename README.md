# BeoOS

BeoOS is the multi-business operating system for Beo companies. Module 1 implements the production foundation and the Beo Art Studio AI Email Assistant.

## Structure

```text
frontend/                  Next.js 15, TypeScript, Tailwind, shadcn/ui, Clerk
backend/app/api/           FastAPI routes
backend/app/domain/        Typed business contracts
backend/app/services/      Zoho, OpenAI, policy, alert, and sync services
backend/app/infrastructure SQLAlchemy database layer
backend/prompts/           Versioned AI prompts
database/migrations/       PostgreSQL/Alembic migrations
docs/modules/              Approved module specifications
```

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

4. Start the mailbox worker in a second terminal:

   ```powershell
   cd backend
   .\.venv\Scripts\python.exe -m app.worker
   ```

5. Install and run the frontend:

   ```powershell
   cd frontend
   npm.cmd install
   npm.cmd run dev
   ```

## External configuration

- **Clerk:** add the frontend URLs, then set the publishable key, secret key, issuer, and JWKS URL.
- **Zoho:** register a server OAuth client. Callback: `BACKEND_URL/api/v1/integrations/zoho/callback`. Use the Zoho accounts/mail base domains matching the mailbox data centre.
- **OpenAI:** set `OPENAI_API_KEY`; `OPENAI_MODEL` can override the documented default.
- **Resend:** verify the alert-sending domain and set `RESEND_API_KEY`.
- **Supabase:** follow [SUPABASE_SETUP.md](SUPABASE_SETUP.md).

## Deployment

Deploy `frontend/` to Vercel. Deploy `backend/` to Railway twice:

- API service: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Worker service: `python -m app.worker`

Run `alembic -c alembic.ini upgrade head` as a single pre-deploy/release command. Both Railway services use the same environment variables and Supabase `DATABASE_URL`.

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


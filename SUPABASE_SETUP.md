# Supabase setup for BeoOS

BeoOS uses Supabase as managed PostgreSQL. The frontend does not query customer-email tables directly; all access passes through the authenticated FastAPI service.

## 1. Create the project

Create a Supabase project in the region closest to the Railway deployment. Save the database password in a password manager.

For Railway, use the Supabase **session pooler** connection string when direct IPv6 connectivity is unavailable. Change its scheme for SQLAlchemy:

```text
postgresql+asyncpg://postgres.PROJECT_REF:URL_ENCODED_PASSWORD@HOST:5432/postgres
```

Copy the username, project reference, host, port, and database name directly from Supabase;
do not type placeholder text such as `PROJECT_REF` into Railway. Replace only the password
placeholder, URL-encoding password characters when necessary, and change the URI scheme from
`postgresql://` to `postgresql+asyncpg://`.

Set this as `DATABASE_URL` in the Railway API and worker services. Never expose it as a `NEXT_PUBLIC_` variable.

## 2. Apply migrations

From `backend/`:

```powershell
.\.venv\Scripts\alembic.exe -c alembic.ini upgrade head
```

The migration creates the multi-business email schema and enables Row Level Security on all business and client-data tables. There are deliberately no Supabase client policies: browser clients cannot read these tables. The Railway database connection must use the project database owner/service connection.

## 3. Seed Beo Art Studio

Set `BOOTSTRAP_CLERK_USER_ID` to Benjamin's Clerk user ID, then run:

```powershell
.\.venv\Scripts\python.exe -m app.seed
```

This creates Beo Art Studio, owner access, the confirmed WhatsApp routing number, signature rules, and the approved service-page price catalogue.

## 4. Storage

Module 1 stores attachment metadata only. Before attachment downloading is enabled, create a private bucket named `email-attachments`. Files must be uploaded by the backend using the Supabase service role, with signed URLs generated only after business-membership checks.

## Security checks

- Keep the database password and Supabase service key in Railway only.
- Do not add public RLS policies to email, contact, draft, or audit tables.
- Rotate database credentials after any accidental exposure.
- Run migrations from one deployment step only, never concurrently from API replicas.

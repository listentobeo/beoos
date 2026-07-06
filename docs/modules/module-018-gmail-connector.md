# Module 1.8: Gmail / Google Workspace Connector

Module 1.8 lets each BeoOS business connect a Gmail or Google Workspace mailbox as an alternative to Zoho Mail.

## What it does

- Adds Google OAuth start/callback routes:
  - `GET /api/v1/integrations/google/start`
  - `GET /api/v1/integrations/google/callback`
- Verifies the authorized Google email matches the selected business primary email.
- Stores Gmail access and refresh tokens encrypted in the existing `mailbox_connections` table.
- Imports Gmail Inbox messages into the unified BeoOS inbox.
- Imports Sent messages on first sync so existing clients can be detected.
- Reuses existing BeoOS AI intake, contacts, threads, drafts, approvals, and push notifications.
- Sends approved Gmail replies through the Gmail API.

## Tenant model

Gmail is tenant-scoped through the existing business mailbox model:

```text
business -> mailbox_connection(provider="gmail") -> threads/messages/contacts
```

Each business connects its own mailbox. Gmail messages are saved under that business only and appear in the same dashboard inbox as Zoho, WhatsApp, and website forms.

## Required variables

```env
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_ACCOUNTS_BASE_URL=https://accounts.google.com
GOOGLE_TOKEN_URL=https://oauth2.googleapis.com/token
GOOGLE_USERINFO_URL=https://openidconnect.googleapis.com/v1/userinfo
GOOGLE_GMAIL_BASE_URL=https://gmail.googleapis.com
```

## Google Cloud setup

1. Create or open a Google Cloud project.
2. Enable Gmail API.
3. Configure OAuth consent screen.
4. Create OAuth Client ID for a web application.
5. Add the backend callback:

   ```text
   https://beoos-production.up.railway.app/api/v1/integrations/google/callback
   ```

6. Add your dashboard users as test users while the OAuth app is in testing mode.
7. Put `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in Railway.

## Scopes

```text
openid
email
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.send
```

For a private/internal BeoOS deployment, Google testing mode is enough for listed test users. For a public SaaS where outside businesses connect Gmail, Google OAuth verification will likely be required.

## Not included yet

- Gmail Pub/Sub watch for instant email webhooks.
- Automatic scheduled Gmail sync worker.
- Gmail labels/actions such as archive, mark read, or star.

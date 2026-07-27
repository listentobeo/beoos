# WhatsApp Business app coexistence

BeoOS supports Meta Embedded Signup v4 for businesses that want to keep using an existing
WhatsApp Business app number while also connecting it to Cloud API.

## Meta configuration

1. Use a Tech Provider or Solution Partner Meta app.
2. Create an Embedded Signup v4 configuration that enables onboarding WhatsApp Business app
   users. Store its ID as `META_WHATSAPP_COEXISTENCE_CONFIG_ID`.
3. Set `WHATSAPP_COEXISTENCE_ENABLED=true`.
4. Subscribe the app to `messages`, `history`, `smb_app_state_sync`, `smb_message_echoes`, and
   `account_update`.
5. Configure `/api/v1/webhooks/whatsapp` as the callback and configure the matching verify token.
6. Keep `META_APP_SECRET` configured in staging and production; unsigned webhook delivery is
   rejected in those environments.

The standard Cloud API-only configuration remains separate. BeoOS does not fall back to that
configuration when a user explicitly chooses coexistence.

## Onboarding sequence

BeoOS creates a tenant- and user-bound signup attempt, opens Meta's v4 configuration, and accepts
coexistence only when session logging returns `FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING`, version
`3`, an exchangeable authorization code, and a WABA ID. It exchanges the code, resolves the exact
selected number, subscribes the WABA, and verifies `is_on_biz_app=true` and
`platform_type=CLOUD_API`. It deliberately skips phone registration.

The encrypted tenant token and verified assets are stored on the tenant connection. Two durable,
idempotent jobs immediately request contacts and history synchronization. Returned Meta request
IDs and the 24-hour deadline are retained for operations and support.

## Webhook processing

The HTTP callback verifies the Meta signature, stores an idempotent event, queues processing, and
acknowledges without running AI or importing a large history payload inline. The worker handles:

- inbound `messages`;
- ordered history metadata (`phase`, `chunk_order`, and `progress`);
- WhatsApp Business app `message_echoes` as outbound messages;
- contact additions, edits, and removals from `smb_app_state_sync`;
- message edits, revokes, and delayed history media;
- `PARTNER_REMOVED`, `ACCOUNT_OFFBOARDED`, and `ACCOUNT_RECONNECTED`;
- history-sharing refusal `2593109` and unsupported-message condition `131060`.

Historical and business-app messages never trigger inbound AI intake. Provider message IDs and
webhook event keys prevent duplicate imports.

## Operations

Monitor the connection's contacts/history status, request IDs, sync deadline, phase, progress,
worker retries, and webhook dead letters. History is complete only when Meta reports phase `2`
with progress `100`. If the 24-hour window expires or a synchronization job dead-letters, the
connection moves to `action_required`; the business must be offboarded in the WhatsApp Business
app and complete signup again.

When Meta sends a disconnection event, BeoOS disables the connection but retains the encrypted
credential and audit evidence until normal retention/deletion procedures apply.

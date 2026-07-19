# BeoOS Remote MCP Server

BeoOS exposes a tenant-scoped MCP-compatible JSON-RPC endpoint so external AI clients can safely read business operating data.

## Endpoint

```text
POST https://beoos-production.up.railway.app/api/v1/mcp
```

Use either header:

```http
Authorization: Bearer beoos_xxx
```

or:

```http
X-BeoOS-API-Key: beoos_xxx
```

External tokens are created per business from:

```text
POST /api/v1/businesses/{business_id}/external-access/tokens
```

The raw token is shown once. BeoOS stores only a hash and prefix.

## First release scope

This first MCP release is intentionally read-only. It lets ChatGPT, Claude, Cursor, Codex, VS Code, and other MCP-compatible clients inspect tenant data without sending messages or changing records.

Available tools:

- `get_business_profile`
- `get_operating_summary`
- `list_inbox_threads`
- `list_crm_leads`
- `list_price_catalogue`
- `list_quotes`
- `list_marketing_metrics`

## Example initialize request

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {}
}
```

## Example list tools request

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

## Example call

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "get_operating_summary",
    "arguments": {}
  }
}
```

## Security model

- Each token belongs to one BeoOS business tenant.
- Each token has scopes such as `inbox:read`, `crm:read`, `quotes:read`, and `marketing:read`.
- Tokens can be revoked.
- Tokens can expire.
- Raw token values are never stored.
- Write/send tools should only be added later with explicit confirmation and audit logs.

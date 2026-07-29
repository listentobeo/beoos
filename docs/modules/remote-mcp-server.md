# BeoOS Remote MCP Server

BeoOS exposes a stateless Streamable HTTP-compatible JSON-RPC endpoint for tenant-scoped
business intelligence.

## Endpoint and authentication

Production endpoint:

```text
https://beoos-production.up.railway.app/api/v1/mcp
```

Transport: HTTPS `POST`, JSON-RPC 2.0, MCP protocol `2025-06-18`. The server returns JSON for
requests and HTTP `202` for notifications. It is stateless and does not provide a server-sent
event stream.

Use one of these headers:

```http
Authorization: Bearer <BEOOS_TOKEN>
MCP-Protocol-Version: 2025-06-18
```

or:

```http
X-BeoOS-API-Key: <BEOOS_TOKEN>
MCP-Protocol-Version: 2025-06-18
```

Create, rotate, and revoke tokens from **Dashboard → Settings → External AI access / MCP**.
The raw value is shown only when it is created or rotated.

## Security behavior

- A token belongs to exactly one business.
- `business_id` is derived from the token and is not accepted in tool inputs.
- Token use revalidates the creator's current membership in the business.
- Raw tokens are HMAC-hashed; only the hash and a display prefix are stored.
- Revoked and expired tokens are rejected.
- Unknown and wildcard scopes cannot be issued.
- Read tools require `marketing:read`; proposal tools separately require
  `marketing:propose`.
- Valid-token MCP requests are durably audited with tenant, token ID, tool/method,
  correlation ID, timestamp, status, latency, and safe error details.
- The default limit is 60 calls per token per rolling minute and 20 seconds per tool call.
- MCP tools never read connector credentials and never accept a caller-supplied tenant ID.

## Marketing read tools

- `marketing.get_summary`
- `marketing.list_properties`
- `marketing.get_page_performance`
- `marketing.get_query_performance`
- `marketing.get_branded_searches`
- `marketing.list_opportunities`
- `marketing.get_opportunity`
- `marketing.list_experiments`
- `marketing.get_experiment`
- `marketing.compare_periods`
- `marketing.get_content_clusters`
- `marketing.get_data_freshness`

Legacy read tools remain available:

- `get_business_profile`
- `get_operating_summary`
- `list_inbox_threads`
- `list_crm_leads`
- `list_price_catalogue`
- `list_quotes`
- `list_marketing_metrics`

## Controlled proposal tools

These require an explicitly issued `marketing:propose` scope:

- `marketing.propose_opportunity`
- `marketing.create_experiment_draft`
- `marketing.request_experiment_approval`
- `marketing.record_manual_implementation`

They only create or update internal BeoOS proposals and records. They cannot publish to
Blogger, edit websites, change Search Console, post to social networks, or spend advertising
money.

## Generic client configuration

Use this shape in clients that support remote HTTP MCP servers with static headers:

```json
{
  "mcpServers": {
    "beoos": {
      "type": "http",
      "url": "https://beoos-production.up.railway.app/api/v1/mcp",
      "headers": {
        "Authorization": "Bearer ${BEOOS_MCP_TOKEN}"
      }
    }
  }
}
```

Keep the token in the client's secret/environment facility rather than committing it to a
configuration file. Clients that require OAuth discovery and do not support static bearer
headers need an OAuth gateway before they can connect directly.

## Secret-free smoke test

```bash
curl -X POST "$BEOOS_MCP_URL" \
  -H "Authorization: Bearer $BEOOS_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "MCP-Protocol-Version: 2025-06-18" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

Never paste a real token into logs, screenshots, tickets, documentation, or source control.

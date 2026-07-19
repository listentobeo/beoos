"use client";

import { useEffect, useState } from "react";
import { KeyRound, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";

const API_URL = "/api/beoos";

const DEFAULT_SCOPES = [
  "business:read",
  "inbox:read",
  "crm:read",
  "pricing:read",
  "quotes:read",
  "analytics:read",
  "marketing:read",
];

type ExternalToken = {
  id: string;
  name: string;
  token_prefix: string;
  scopes: string[];
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string;
};

type CreatedToken = ExternalToken & { token: string };

export function ExternalAccessCard({ businessId }: { businessId: string }) {
  const [tokens, setTokens] = useState<ExternalToken[]>([]);
  const [name, setName] = useState("ChatGPT / Claude MCP");
  const [createdToken, setCreatedToken] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    void loadTokens();
  }, [businessId]);

  async function loadTokens() {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/businesses/${businessId}/external-access/tokens`, {
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`Could not load tokens (${response.status}).`);
      setTokens(await response.json());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not load external tokens.");
    } finally {
      setLoading(false);
    }
  }

  async function createToken() {
    setCreating(true);
    setMessage(null);
    setCreatedToken(null);
    try {
      const response = await fetch(`${API_URL}/businesses/${businessId}/external-access/tokens`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, scopes: DEFAULT_SCOPES, expires_in_days: 365 }),
      });
      if (!response.ok) throw new Error(`Could not create token (${response.status}).`);
      const created = await response.json() as CreatedToken;
      setCreatedToken(created.token);
      setMessage("External AI token created. Copy it now; BeoOS will not show it again.");
      await loadTokens();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not create token.");
    } finally {
      setCreating(false);
    }
  }

  async function revokeToken(tokenId: string) {
    setMessage(null);
    try {
      const response = await fetch(
        `${API_URL}/businesses/${businessId}/external-access/tokens/${tokenId}`,
        { method: "DELETE" },
      );
      if (!response.ok) throw new Error(`Could not revoke token (${response.status}).`);
      setMessage("External AI token revoked.");
      await loadTokens();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not revoke token.");
    }
  }

  return (
    <div className="mt-5 rounded-2xl border bg-white p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex gap-3">
          <div className="grid size-10 place-items-center rounded-xl bg-[#fff0ea] text-[#ed633f]">
            <KeyRound className="size-4" />
          </div>
          <div>
            <h3 className="font-semibold">External AI access / MCP</h3>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-[#777c76]">
              Create a tenant-scoped token for ChatGPT, Claude, Cursor, Codex, or VS Code to read
              this business through the BeoOS MCP server. This first version is read-only.
            </p>
          </div>
        </div>
        <Button type="button" onClick={createToken} disabled={creating} size="sm">
          {creating ? "Creating..." : "Create MCP token"}
        </Button>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]">
        <label className="text-xs font-semibold text-[#646a64]">
          Token name
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="mt-1.5 w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[#ed633f]/25"
          />
        </label>
        <div className="rounded-xl bg-[#f7f6f2] p-3 text-xs leading-5 text-[#777c76]">
          MCP endpoint
          <code className="block break-all font-semibold text-[#262a31]">/api/v1/mcp</code>
        </div>
      </div>

      {createdToken && (
        <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-900">
          <p className="font-bold">Copy this token now</p>
          <code className="mt-2 block break-all rounded-lg bg-white p-2 text-[#262a31]">
            {createdToken}
          </code>
        </div>
      )}

      {message && <p className="mt-3 text-xs text-[#747973]">{message}</p>}

      <div className="mt-4 overflow-hidden rounded-xl border">
        <div className="grid grid-cols-[1fr_auto_auto] gap-3 bg-[#f7f6f2] px-3 py-2 text-[11px] font-bold uppercase tracking-[0.12em] text-[#777c76]">
          <span>Token</span>
          <span>Status</span>
          <span>Action</span>
        </div>
        {loading ? (
          <p className="px-3 py-4 text-sm text-[#777c76]">Loading tokens...</p>
        ) : tokens.length ? (
          tokens.map((token) => (
            <div key={token.id} className="grid grid-cols-[1fr_auto_auto] items-center gap-3 border-t px-3 py-3 text-sm">
              <div>
                <p className="font-semibold">{token.name}</p>
                <p className="mt-1 text-xs text-[#777c76]">
                  {token.token_prefix}... · {token.scopes.length} scopes · expires {formatDate(token.expires_at)}
                </p>
              </div>
              <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${token.revoked_at ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"}`}>
                {token.revoked_at ? "Revoked" : "Active"}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={Boolean(token.revoked_at)}
                onClick={() => revokeToken(token.id)}
              >
                <Trash2 className="size-4" />
              </Button>
            </div>
          ))
        ) : (
          <p className="px-3 py-4 text-sm text-[#777c76]">No external AI tokens yet.</p>
        )}
      </div>
    </div>
  );
}

function formatDate(value: string | null) {
  if (!value) return "never";
  return new Date(value).toLocaleDateString();
}


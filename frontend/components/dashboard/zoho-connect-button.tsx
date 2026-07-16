"use client";

import { useState } from "react";
import { LoaderCircle, MailPlus } from "lucide-react";
import { Button } from "@/components/ui/button";

const API_URL = "/api/beoos";

export function ZohoConnectButton({ businessId }: { businessId: string }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function connect() {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `${API_URL}/integrations/zoho/start?business_id=${businessId}`,
        {},
      );
      if (!response.ok) throw new Error("Unable to begin Zoho connection");
      const data = (await response.json()) as { authorization_url: string };
      window.location.assign(data.authorization_url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to connect Zoho Mail");
      setLoading(false);
    }
  }

  return (
    <div>
      <Button onClick={connect} disabled={loading}>
        {loading ? <LoaderCircle className="size-4 animate-spin" /> : <MailPlus className="size-4" />}
        Connect Zoho Mail
      </Button>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  );
}

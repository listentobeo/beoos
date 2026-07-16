"use client";

import { useState } from "react";
import { LoaderCircle, MailPlus } from "lucide-react";
import { Button } from "@/components/ui/button";

const API_URL = "/api/beoos";

export function GmailConnectButton({ businessId }: { businessId: string }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function connect() {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/integrations/google/start?business_id=${businessId}`, {
      });
      if (!response.ok) throw new Error("Unable to begin Gmail connection");
      const data = (await response.json()) as { authorization_url: string };
      window.location.assign(data.authorization_url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to connect Gmail");
      setLoading(false);
    }
  }

  return (
    <div>
      <Button onClick={connect} disabled={loading} variant="outline">
        {loading ? <LoaderCircle className="size-4 animate-spin" /> : <MailPlus className="size-4" />}
        Connect Gmail
      </Button>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  );
}

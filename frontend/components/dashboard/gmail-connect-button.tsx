"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { LoaderCircle, MailPlus } from "lucide-react";
import { Button } from "@/components/ui/button";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export function GmailConnectButton({ businessId }: { businessId: string }) {
  const { getToken } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function connect() {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const response = await fetch(`${API_URL}/integrations/google/start?business_id=${businessId}`, {
        headers: { Authorization: `Bearer ${token}` },
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

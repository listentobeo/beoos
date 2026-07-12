"use client";

import { useState } from "react";
import { CheckCircle2, LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export function AcceptQuoteButton({
  publicToken,
  accepted,
  paymentUrl,
}: {
  publicToken: string;
  accepted: boolean;
  paymentUrl: string | null;
}) {
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(accepted);
  const [url, setUrl] = useState(paymentUrl);
  const [message, setMessage] = useState<string | null>(null);

  async function acceptQuote() {
    setLoading(true);
    setMessage(null);
    try {
      const response = await fetch(`${API_URL}/quotes/${publicToken}/accept`, {
        method: "POST",
      });
      if (!response.ok) throw new Error("Proposal could not be accepted.");
      const result = (await response.json()) as { payment_url?: string | null };
      setDone(true);
      setUrl(result.payment_url || null);
      setMessage("Proposal accepted.");
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Proposal could not be accepted.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3">
      <Button onClick={acceptQuote} disabled={loading || done} className="w-full">
        {loading ? <LoaderCircle className="size-4 animate-spin" /> : <CheckCircle2 className="size-4" />}
        {done ? "Proposal accepted" : "Accept proposal"}
      </Button>
      {url && (
        <Button asChild variant="outline" className="w-full">
          <a href={url}>Pay deposit</a>
        </Button>
      )}
      {message && <p className="text-center text-xs text-[#747973]">{message}</p>}
    </div>
  );
}

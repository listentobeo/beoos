"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { CreditCard, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export function QuotePaymentButton({
  businessId,
  quoteId,
  hasPaymentUrl,
}: {
  businessId: string;
  quoteId: string;
  hasPaymentUrl: boolean;
}) {
  const { getToken } = useAuth();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function createPaymentLink() {
    setLoading(true);
    setMessage(null);
    try {
      const token = await getToken();
      const response = await fetch(
        `${API_URL}/businesses/${businessId}/quotes/${quoteId}/payment-link`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      if (!response.ok) {
        const error = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(error?.detail || "Payment link could not be created.");
      }
      setMessage("Payment link ready.");
      router.refresh();
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Payment link could not be created.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <Button onClick={createPaymentLink} disabled={loading || hasPaymentUrl} className="w-full">
        {loading ? <LoaderCircle className="size-4 animate-spin" /> : <CreditCard className="size-4" />}
        {hasPaymentUrl ? "Payment link ready" : "Create Paystack link"}
      </Button>
      {message && <p className="mt-2 text-xs text-[#747973]">{message}</p>}
    </div>
  );
}

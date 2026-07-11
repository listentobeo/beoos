"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { FileText, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export function CreateQuoteButton({
  businessId,
  leadId,
}: {
  businessId: string;
  leadId: string;
}) {
  const { getToken } = useAuth();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function createQuote() {
    setLoading(true);
    setMessage(null);
    try {
      const token = await getToken();
      const response = await fetch(
        `${API_URL}/businesses/${businessId}/quotes/from-lead/${leadId}`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      if (!response.ok) {
        let detail = "";
        try {
          const error = (await response.json()) as { detail?: string };
          detail = error.detail ? ` ${error.detail}` : "";
        } catch {}
        throw new Error(`Quote could not be created.${detail}`);
      }
      const quote = (await response.json()) as { id: string };
      router.push(`/dashboard/quotes/${quote.id}`);
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Quote could not be created.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <Button onClick={createQuote} disabled={loading} size="sm" className="w-full">
        {loading ? <LoaderCircle className="size-4 animate-spin" /> : <FileText className="size-4" />}
        Create quote
      </Button>
      {message && <p className="mt-2 text-xs text-[#b5472f]">{message}</p>}
    </div>
  );
}

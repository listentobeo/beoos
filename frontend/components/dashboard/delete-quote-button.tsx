"use client";

import { useState } from "react";
import { LoaderCircle, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

const API_URL = "/api/beoos";

export function DeleteQuoteButton({ businessId, quoteId }: { businessId: string; quoteId: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function deleteQuote() {
    if (
      !confirm(
        "Delete this quote permanently? The linked CRM lead and customer conversation will stay.",
      )
    ) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/businesses/${businessId}/quotes/${quoteId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "The quote could not be deleted.");
      }
      router.replace("/dashboard/quotes");
      router.refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The quote could not be deleted.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <Button
        type="button"
        variant="outline"
        onClick={deleteQuote}
        disabled={loading}
        className="w-full border-red-200 text-red-700 hover:bg-red-50"
      >
        {loading ? <LoaderCircle className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
        Delete quote
      </Button>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  );
}

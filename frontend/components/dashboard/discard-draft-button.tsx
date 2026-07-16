"use client";

import { useState } from "react";
import { LoaderCircle, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

export function DiscardDraftButton({ businessId, draftId }: { businessId: string; draftId: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function discard() {
    if (!confirm("Discard this AI draft? The customer message will stay in the inbox.")) return;
    setLoading(true);
    setError(null);
    try {
      const apiUrl = "/api/beoos";
      const response = await fetch(`${apiUrl}/businesses/${businessId}/email/drafts/${draftId}/discard`, {
        method: "POST",
      });
      if (!response.ok) throw new Error("The draft could not be discarded");
      router.refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The draft could not be discarded");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="text-right">
      <Button type="button" variant="outline" onClick={discard} disabled={loading}>
        {loading ? <LoaderCircle className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
        Discard
      </Button>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  );
}

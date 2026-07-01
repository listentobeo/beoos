"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { Check, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

export function ApproveDraftButton({ businessId, draftId }: { businessId: string; draftId: string }) {
  const { getToken } = useAuth();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function approve() {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
      const response = await fetch(`${apiUrl}/businesses/${businessId}/email/drafts/${draftId}/approve`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error("The draft could not be sent");
      router.refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The draft could not be sent");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="text-right">
      <Button onClick={approve} disabled={loading}>
        {loading ? <LoaderCircle className="size-4 animate-spin" /> : <Check className="size-4" />}
        Approve and send
      </Button>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  );
}


"use client";

import { useState } from "react";
import { ClipboardList, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

const API_URL = "/api/beoos";

export function CreateLeadButton({
  businessId,
  threadId,
  isDeal,
}: {
  businessId: string;
  threadId: string;
  isDeal: boolean;
}) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function createLead() {
    setLoading(true);
    setMessage(null);
    try {
      const response = await fetch(`${API_URL}/businesses/${businessId}/crm/threads/${threadId}/lead`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          stage: isDeal ? "qualified" : "new",
          notes: "Created from BeoOS inbox conversation.",
        }),
      });
      if (!response.ok) {
        let detail = "";
        try {
          const error = (await response.json()) as { detail?: string };
          detail = error.detail ? ` ${error.detail}` : "";
        } catch {}
        throw new Error(`Lead could not be created.${detail}`);
      }
      setMessage("CRM lead created.");
      router.refresh();
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Lead could not be created.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <Button onClick={createLead} disabled={loading} className="w-full">
        {loading ? <LoaderCircle className="size-4 animate-spin" /> : <ClipboardList className="size-4" />}
        Create CRM lead
      </Button>
      {message && <p className="mt-2 text-xs text-[#747973]">{message}</p>}
    </div>
  );
}

"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { ClipboardList, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export function CreateLeadButton({
  businessId,
  threadId,
  isDeal,
}: {
  businessId: string;
  threadId: string;
  isDeal: boolean;
}) {
  const { getToken } = useAuth();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function createLead() {
    setLoading(true);
    setMessage(null);
    try {
      const token = await getToken();
      const response = await fetch(`${API_URL}/businesses/${businessId}/crm/threads/${threadId}/lead`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
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

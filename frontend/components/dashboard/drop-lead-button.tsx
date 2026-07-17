"use client";

import { LoaderCircle, XCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";

const API_URL = "/api/beoos";

export function DropLeadButton({
  businessId,
  leadId,
}: {
  businessId: string;
  leadId: string;
}) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function dropLead() {
    const reason =
      window.prompt(
        "Why are we dropping this lead? This closes it as Lost and cancels scheduled follow-ups.",
        "Not a good fit",
      ) ?? "";
    if (!reason.trim()) return;
    setLoading(true);
    setMessage(null);
    try {
      const response = await fetch(`${API_URL}/businesses/${businessId}/crm/leads/${leadId}/drop`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
      });
      if (!response.ok) throw new Error(`Could not drop lead (${response.status}).`);
      setMessage("Lead dropped from active pipeline.");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not drop lead.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="w-full justify-center border-red-100 text-red-700 hover:bg-red-50"
        onClick={dropLead}
        disabled={loading}
      >
        {loading ? <LoaderCircle className="size-4 animate-spin" /> : <XCircle className="size-4" />}
        Drop lead
      </Button>
      {message && <p className="mt-2 text-xs text-[#747973]">{message}</p>}
    </div>
  );
}

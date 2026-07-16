"use client";

import { useState } from "react";
import { CalendarClock, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

const API_URL = "/api/beoos";

export function ScheduleFollowUpButton({
  businessId,
  leadId,
  hasExistingFollowUp,
}: {
  businessId: string;
  leadId: string;
  hasExistingFollowUp: boolean;
}) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function schedule(cadence: "standard" | "hot") {
    setLoading(true);
    setMessage(null);
    try {
      const response = await fetch(`${API_URL}/businesses/${businessId}/crm/leads/${leadId}/follow-ups`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ cadence }),
      });
      if (!response.ok) {
        let detail = "";
        try {
          const error = (await response.json()) as { detail?: string };
          detail = error.detail ? ` ${error.detail}` : "";
        } catch {}
        throw new Error(`Follow-up could not be scheduled.${detail}`);
      }
      const result = (await response.json()) as { tasks_created: number };
      setMessage(`${result.tasks_created} follow-ups scheduled.`);
      router.refresh();
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Follow-up could not be scheduled.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={loading}
          onClick={() => schedule("standard")}
          className="w-full"
        >
          {loading ? <LoaderCircle className="size-4 animate-spin" /> : <CalendarClock className="size-4" />}
          {hasExistingFollowUp ? "Reset" : "Follow up"}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={loading}
          onClick={() => schedule("hot")}
          className="w-full"
        >
          Hot lead
        </Button>
      </div>
      {message && <p className="text-xs text-[#747973]">{message}</p>}
    </div>
  );
}

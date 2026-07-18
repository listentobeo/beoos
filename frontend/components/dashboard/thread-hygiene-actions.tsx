"use client";

import { Archive, LoaderCircle, RotateCcw, ShieldX } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";

const API_URL = "/api/beoos";

export function ThreadHygieneActions({
  businessId,
  threadId,
  category,
  status,
}: {
  businessId: string;
  threadId: string;
  category: string;
  status: string;
}) {
  const router = useRouter();
  const [loading, setLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function act(action: "archive" | "spam" | "restore") {
    const reason =
      action === "restore"
        ? ""
        : window.prompt(
            action === "spam"
              ? "Why should this move to spam/noise?"
              : "Why should this leave the active inbox?",
            action === "spam" ? "Not business relevant" : "Handled / no action needed",
          ) ?? "";
    if (action !== "restore" && !reason.trim()) return;
    setLoading(action);
    setMessage(null);
    try {
      const response = await fetch(`${API_URL}/businesses/${businessId}/email/threads/${threadId}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: action === "restore" ? undefined : JSON.stringify({ reason }),
      });
      if (!response.ok) throw new Error(`Could not ${action} thread (${response.status}).`);
      setMessage(
        action === "spam"
          ? "Moved to spam/noise."
          : action === "archive"
            ? "Archived from active inbox."
            : "Restored to active inbox.",
      );
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Thread action failed.");
    } finally {
      setLoading(null);
    }
  }

  const canRestore = category === "spam" || status === "closed";

  return (
    <div className="space-y-2">
      {canRestore ? (
        <Button type="button" variant="outline" size="sm" className="w-full" onClick={() => act("restore")} disabled={Boolean(loading)}>
          {loading === "restore" ? <LoaderCircle className="size-4 animate-spin" /> : <RotateCcw className="size-4" />}
          Restore to inbox
        </Button>
      ) : (
        <>
          <Button type="button" variant="outline" size="sm" className="w-full" onClick={() => act("archive")} disabled={Boolean(loading)}>
            {loading === "archive" ? <LoaderCircle className="size-4 animate-spin" /> : <Archive className="size-4" />}
            Archive thread
          </Button>
          <Button type="button" variant="outline" size="sm" className="w-full border-red-100 text-red-700 hover:bg-red-50" onClick={() => act("spam")} disabled={Boolean(loading)}>
            {loading === "spam" ? <LoaderCircle className="size-4 animate-spin" /> : <ShieldX className="size-4" />}
            Move to spam
          </Button>
        </>
      )}
      {message && <p className="text-xs text-[#747973]">{message}</p>}
    </div>
  );
}

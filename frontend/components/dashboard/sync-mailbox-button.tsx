"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LoaderCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

const API_URL = "/api/beoos";

type SyncResult = {
  success?: boolean;
  mailboxes_checked?: number;
  messages_fetched?: number;
  messages_created?: number;
  duplicates_skipped?: number;
  imported?: number;
  message_count?: number;
};

export function SyncMailboxButton({ businessId }: { businessId: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function syncNow() {
    setLoading(true);
    setMessage(null);
    try {
      const response = await fetch(`${API_URL}/businesses/${businessId}/email/mailbox/sync`, {
        method: "POST",
      });
      if (!response.ok) {
        let detail = "";
        try {
          const error = (await response.json()) as { detail?: string };
          detail = error.detail ? ` ${error.detail}` : "";
        } catch {}
        throw new Error(response.status === 404 ? "Connect Zoho Mail or Gmail first." : `Sync failed.${detail}`);
      }
      const result = (await response.json()) as SyncResult;
      const created = result.messages_created ?? result.imported ?? 0;
      const fetched = result.messages_fetched;
      const duplicates = result.duplicates_skipped;
      if (typeof fetched === "number" && typeof duplicates === "number") {
        setMessage(
          `Fetched ${fetched}, saved ${created}, skipped ${duplicates} duplicate${duplicates === 1 ? "" : "s"}.`,
        );
      } else {
        setMessage(`Saved ${created} new message${created === 1 ? "" : "s"}.`);
      }
      router.refresh();
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Sync failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-2 sm:items-end">
      <Button onClick={syncNow} disabled={loading} size="sm">
        {loading ? <LoaderCircle className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
        Sync now
      </Button>
      {message && <p className="text-xs text-[#747973]">{message}</p>}
    </div>
  );
}

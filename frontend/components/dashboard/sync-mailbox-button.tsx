"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { LoaderCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export function SyncMailboxButton({ businessId }: { businessId: string }) {
  const { getToken } = useAuth();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function syncNow() {
    setLoading(true);
    setMessage(null);
    try {
      const token = await getToken();
      const response = await fetch(`${API_URL}/businesses/${businessId}/email/mailbox/sync`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        throw new Error(response.status === 404 ? "Connect Zoho Mail first." : "Sync failed.");
      }
      const result = (await response.json()) as { imported: number; message_count: number };
      setMessage(`Synced ${result.imported} new message${result.imported === 1 ? "" : "s"}.`);
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

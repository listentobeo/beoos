"use client";

import { CheckCheck, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";

const API_URL = "/api/beoos";

export function MarkAllReadButton({
  businessId,
  unreadCount,
}: {
  businessId: string;
  unreadCount: number;
}) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function markAllRead() {
    if (unreadCount <= 0) return;
    setLoading(true);
    setMessage(null);
    try {
      const response = await fetch(`${API_URL}/businesses/${businessId}/email/threads/mark-all-read`, {
        method: "POST",
      });
      if (!response.ok) throw new Error("Could not mark inbox as read.");
      const payload = (await response.json()) as { updated?: number };
      setMessage(`${payload.updated ?? 0} conversation${payload.updated === 1 ? "" : "s"} marked read.`);
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not mark inbox as read.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-start gap-1 sm:items-end">
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={markAllRead}
        disabled={loading || unreadCount <= 0}
      >
        {loading ? <LoaderCircle className="size-4 animate-spin" /> : <CheckCheck className="size-4" />}
        Mark all as read
      </Button>
      {message && <p className="text-xs text-[#747973]">{message}</p>}
    </div>
  );
}

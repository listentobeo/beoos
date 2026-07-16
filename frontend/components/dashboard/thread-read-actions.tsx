"use client";

import { useState } from "react";
import { CheckCheck, LoaderCircle, Mail } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

const API_URL = "/api/beoos";

export function ThreadReadActions({
  businessId,
  threadId,
  unreadCount,
}: {
  businessId: string;
  threadId: string;
  unreadCount: number;
}) {
  const router = useRouter();
  const [loading, setLoading] = useState<"read" | "unread" | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function mark(state: "read" | "unread") {
    setLoading(state);
    setMessage(null);
    try {
      const response = await fetch(
        `${API_URL}/businesses/${businessId}/email/threads/${threadId}/mark-${state}`,
      );
      if (!response.ok) throw new Error(`Could not mark thread ${state}.`);
      setMessage(state === "read" ? "Marked as read." : "Marked as unread.");
      router.refresh();
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Read state could not be changed.");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div>
      <div className="grid grid-cols-2 gap-2">
        <Button onClick={() => mark("read")} disabled={loading !== null || unreadCount === 0} size="sm" variant="outline">
          {loading === "read" ? <LoaderCircle className="size-4 animate-spin" /> : <CheckCheck className="size-4" />}
          Mark read
        </Button>
        <Button onClick={() => mark("unread")} disabled={loading !== null} size="sm" variant="outline">
          {loading === "unread" ? <LoaderCircle className="size-4 animate-spin" /> : <Mail className="size-4" />}
          Mark unread
        </Button>
      </div>
      {message && <p className="mt-2 text-xs text-[#747973]">{message}</p>}
    </div>
  );
}

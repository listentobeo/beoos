"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

const API_URL = "/api/beoos";

export function AutoMarkThreadRead({
  businessId,
  threadId,
  unreadCount,
}: {
  businessId: string;
  threadId: string;
  unreadCount: number;
}) {
  const router = useRouter();

  useEffect(() => {
    if (unreadCount <= 0) return;
    const timeout = window.setTimeout(async () => {
      const response = await fetch(
        `${API_URL}/businesses/${businessId}/email/threads/${threadId}/mark-read`,
        { method: "POST" },
      );
      if (response.ok) router.refresh();
    }, 500);
    return () => window.clearTimeout(timeout);
  }, [businessId, threadId, unreadCount, router]);

  return null;
}

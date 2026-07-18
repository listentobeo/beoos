"use client";

import { LoaderCircle } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { InboxTable } from "@/components/dashboard/inbox-table";
import type { Thread } from "@/lib/api";

const API_URL = "/api/beoos";
const PAGE_SIZE = 50;

export function InfiniteThreadList({
  businessId,
  initialThreads,
  filters,
  mailboxConnected = true,
  emptyMessage,
}: {
  businessId: string;
  initialThreads: Thread[];
  filters?: { category?: string; status?: string; provider?: string; search?: string };
  mailboxConnected?: boolean;
  emptyMessage?: string;
}) {
  const [threads, setThreads] = useState(initialThreads);
  const [offset, setOffset] = useState(initialThreads.length);
  const [hasMore, setHasMore] = useState(initialThreads.length >= PAGE_SIZE);
  const [loading, setLoading] = useState(false);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  const filterKey = JSON.stringify(filters ?? {});
  const queryBase = useMemo(() => {
    const params = new URLSearchParams();
    Object.entries(filters ?? {}).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    params.set("limit", String(PAGE_SIZE));
    return params;
  }, [filterKey]);

  useEffect(() => {
    setThreads(initialThreads);
    setOffset(initialThreads.length);
    setHasMore(initialThreads.length >= PAGE_SIZE);
  }, [initialThreads, filterKey]);

  useEffect(() => {
    const target = sentinelRef.current;
    if (!target || !hasMore) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          void loadMore();
        }
      },
      { rootMargin: "280px" },
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [hasMore, loading, offset, queryBase]);

  async function loadMore() {
    if (loading || !hasMore) return;
    setLoading(true);
    try {
      const params = new URLSearchParams(queryBase);
      params.set("offset", String(offset));
      const response = await fetch(
        `${API_URL}/businesses/${businessId}/email/threads?${params.toString()}`,
        { cache: "no-store" },
      );
      if (!response.ok) throw new Error("Could not load more conversations");
      const nextThreads = (await response.json()) as Thread[];
      setThreads((current) => {
        const seen = new Set(current.map((thread) => thread.id));
        return [...current, ...nextThreads.filter((thread) => !seen.has(thread.id))];
      });
      setOffset((current) => current + nextThreads.length);
      setHasMore(nextThreads.length >= PAGE_SIZE);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <InboxTable
        threads={threads}
        mailboxConnected={mailboxConnected}
        emptyMessage={emptyMessage}
      />
      <div ref={sentinelRef} className="flex min-h-12 items-center justify-center border-t px-5 py-3 text-xs text-[#8a8e88]">
        {loading && (
          <span className="inline-flex items-center gap-2">
            <LoaderCircle className="size-3.5 animate-spin" />
            Loading more conversations
          </span>
        )}
        {!loading && hasMore && <span>Scroll for more conversations</span>}
        {!loading && !hasMore && threads.length > 0 && <span>End of conversations</span>}
      </div>
    </>
  );
}

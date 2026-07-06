"use client";

import { Search, X } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";

export function ConversationSearch({ initialQuery = "" }: { initialQuery?: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [pending, startTransition] = useTransition();

  function submit(formData: FormData) {
    const query = String(formData.get("q") ?? "").trim();
    const params = new URLSearchParams(searchParams);
    if (query) params.set("q", query);
    else params.delete("q");
    startTransition(() => {
      router.push(params.size ? `/dashboard/inbox?${params.toString()}` : "/dashboard/inbox");
    });
  }

  function clear() {
    const params = new URLSearchParams(searchParams);
    params.delete("q");
    startTransition(() => {
      router.push(params.size ? `/dashboard/inbox?${params.toString()}` : "/dashboard/inbox");
    });
  }

  return (
    <form action={submit} className="flex items-center gap-2 rounded-xl border bg-[#faf9f6] px-3 py-2 text-sm text-[#777c76] transition focus-within:ring-2 focus-within:ring-[#ed633f]/20 sm:w-80">
      <Search className="size-4 shrink-0" />
      <input
        key={initialQuery}
        name="q"
        defaultValue={initialQuery}
        placeholder="Search conversations"
        className="min-w-0 flex-1 bg-transparent text-[#262a31] outline-none placeholder:text-[#777c76]"
      />
      {initialQuery && (
        <button type="button" onClick={clear} className="rounded-full p-1 text-[#8a8e88] hover:bg-[#ebe8df] hover:text-[#262a31]" aria-label="Clear search">
          <X className="size-3.5" />
        </button>
      )}
      <button type="submit" disabled={pending} className="sr-only">Search</button>
    </form>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import type { Business } from "@/lib/api";

export function BusinessSwitcher({
  businesses,
  activeId,
  className,
}: {
  businesses: Business[];
  activeId: string | null;
  className?: string;
}) {
  const router = useRouter();

  function selectBusiness(id: string) {
    if (!id) return;
    document.cookie = `beoos_business_id=${encodeURIComponent(id)}; path=/; max-age=31536000; samesite=lax`;
    router.refresh();
  }

  return (
    <select
      aria-label="Current business"
      value={activeId ?? ""}
      onChange={(event) => selectBusiness(event.target.value)}
      className={cn("min-w-0 flex-1 appearance-none bg-transparent text-sm font-medium text-white outline-none", className)}
    >
      {businesses.length === 0 && <option value="" className="text-[#171b23]">No business yet</option>}
      {businesses.map((business) => <option key={business.id} value={business.id} className="text-[#171b23]">{business.name}</option>)}
    </select>
  );
}

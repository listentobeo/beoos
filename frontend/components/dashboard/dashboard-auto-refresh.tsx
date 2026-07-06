"use client";

import { useRouter } from "next/navigation";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

const REFRESH_INTERVAL_MS = 15_000;
const SAFE_REFRESH_PATHS = [
  "/dashboard/inbox",
  "/dashboard/whatsapp",
  "/dashboard/urgent",
  "/dashboard/clients",
  "/dashboard/approvals",
];

function canRefreshPath(pathname: string) {
  if (pathname.startsWith("/dashboard/inbox/")) return false;
  return SAFE_REFRESH_PATHS.some((path) => pathname === path);
}

function userIsEditing() {
  const active = document.activeElement;
  if (!active) return false;
  return (
    active instanceof HTMLInputElement ||
    active instanceof HTMLTextAreaElement ||
    active instanceof HTMLSelectElement ||
    active.getAttribute("contenteditable") === "true"
  );
}

export function DashboardAutoRefresh() {
  const router = useRouter();
  const pathname = usePathname();
  const lastRefreshRef = useRef(0);

  useEffect(() => {
    function refresh() {
      if (!canRefreshPath(pathname)) return;
      if (document.visibilityState !== "visible") return;
      if (userIsEditing()) return;
      const now = Date.now();
      if (now - lastRefreshRef.current < 3_000) return;
      lastRefreshRef.current = now;
      router.refresh();
    }

    const interval = window.setInterval(refresh, REFRESH_INTERVAL_MS);
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [pathname, router]);

  return null;
}

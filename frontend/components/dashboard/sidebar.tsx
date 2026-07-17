"use client";

import { SignOutButton, UserButton, useUser } from "@clerk/nextjs";
import {
  BarChart3,
  Building2,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  FilePenLine,
  FileText,
  HelpCircle,
  Inbox,
  LogOut,
  Megaphone,
  MessageCircleMore,
  Search,
  Settings,
  ShieldAlert,
  Tags,
  UsersRound,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { BusinessSwitcher } from "@/components/dashboard/business-switcher";
import { cn } from "@/lib/utils";
import type { Business } from "@/lib/api";

const primary = [
  ["Inbox", "/dashboard/inbox", Inbox],
  ["Needs approval", "/dashboard/approvals", FilePenLine],
  ["Urgent", "/dashboard/urgent", ShieldAlert],
  ["Existing clients", "/dashboard/clients", UsersRound],
  ["WhatsApp inbox", "/dashboard/whatsapp", MessageCircleMore],
] as const;

const manage = [
  ["CRM pipeline", "/dashboard/crm", ClipboardList],
  ["Quotations", "/dashboard/quotes", FileText],
  ["Price catalogue", "/dashboard/prices", Tags],
  ["Analytics", "/dashboard/analytics", BarChart3],
  ["Marketing", "/dashboard/marketing", Megaphone],
  ["Business settings", "/dashboard/settings", Settings],
] as const;

const STORAGE_KEY = "beoos_sidebar_collapsed";

export function Sidebar({
  businesses,
  activeId,
}: {
  businesses: Business[];
  activeId: string | null;
}) {
  const pathname = usePathname();
  const { user } = useUser();
  const [collapsed, setCollapsed] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const allLinks = [...primary, ...manage];

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved === "true") setCollapsed(true);
    setHydrated(true);
  }, []);

  useEffect(() => {
    const width = collapsed ? "88px" : "264px";
    document.documentElement.style.setProperty("--beoos-sidebar-width", width);
    if (hydrated) window.localStorage.setItem(STORAGE_KEY, String(collapsed));
  }, [collapsed, hydrated]);

  function isActive(href: string) {
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  function mobileLinkClass(href: string) {
    const active = isActive(href);
    return `flex shrink-0 items-center gap-2 rounded-xl px-3 py-2 text-xs transition ${
      active
        ? "bg-white text-[#171b23]"
        : "bg-white/[0.06] text-white/70 hover:bg-white/[0.1] hover:text-white"
    }`;
  }

  function desktopLinkClass(href: string) {
    const active = isActive(href);
    return cn(
      "group relative flex items-center rounded-2xl text-sm font-semibold transition",
      collapsed ? "mx-auto size-11 justify-center" : "gap-3 px-3 py-2.5",
      active
        ? "bg-[#fff0ea] text-[#ed633f] shadow-[0_8px_20px_rgba(237,99,63,0.10)]"
        : "text-[#60708a] hover:bg-[#f5f7fb] hover:text-[#172033]",
    );
  }

  const displayName =
    user?.fullName ??
    user?.primaryEmailAddress?.emailAddress?.split("@")[0] ??
    "BeoOS user";
  const initials = displayName
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();

  return (
    <>
      <div className="fixed inset-x-0 top-0 z-30 border-b border-white/10 bg-[#101827] px-4 py-3 text-white lg:hidden">
        <div className="flex items-center gap-3">
          <div className="grid size-9 place-items-center rounded-xl bg-[#ed633f] text-sm font-black tracking-tight">
            B
          </div>
          <div className="min-w-0">
            <p className="text-sm font-bold tracking-tight">BeoOS</p>
            <p className="truncate text-[10px] text-white/45">Unified business command center</p>
          </div>
          <div className="ml-auto" aria-label="Account menu">
            <UserButton />
          </div>
        </div>

        <div className="mt-3 flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.06] px-3 py-2.5">
          <Building2 className="size-4 shrink-0 text-[#f69a7e]" />
          <BusinessSwitcher businesses={businesses} activeId={activeId} />
        </div>

        <nav className="-mx-1 mt-3 flex gap-2 overflow-x-auto px-1 pb-1">
          {allLinks.map(([label, href, Icon]) => (
            <Link key={href} href={href} className={mobileLinkClass(href)}>
              <Icon className="size-3.5" />
              {label}
            </Link>
          ))}
        </nav>
      </div>

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-20 hidden flex-col border-r border-[#e7ebf2] bg-white text-[#172033] shadow-[12px_0_40px_rgba(15,23,42,0.04)] transition-[width] duration-300 ease-out lg:flex",
          collapsed ? "w-[88px]" : "w-[264px]",
        )}
      >
        <div className="flex h-full min-h-0 flex-col">
          <div className={cn("flex items-center border-b border-[#edf0f5] p-4", collapsed ? "justify-center" : "gap-3")}>
            <div className="grid size-10 shrink-0 place-items-center rounded-2xl bg-[#ed633f] text-sm font-black text-white shadow-[0_12px_22px_rgba(237,99,63,0.25)]">
              B
            </div>
            {!collapsed && (
              <div className="min-w-0">
                <p className="truncate text-base font-black tracking-[-0.04em]">BeoOS</p>
                <p className="truncate text-[11px] font-medium text-[#7b8799]">
                  Business command center
                </p>
              </div>
            )}
            {!collapsed && (
              <button
                type="button"
                onClick={() => setCollapsed(true)}
                className="ml-auto grid size-8 place-items-center rounded-xl text-[#7b8799] transition hover:bg-[#f5f7fb] hover:text-[#172033]"
                aria-label="Collapse sidebar"
              >
                <ChevronLeft className="size-4" />
              </button>
            )}
          </div>

          {collapsed && (
            <button
              type="button"
              onClick={() => setCollapsed(false)}
              className="mx-auto mt-4 grid size-10 place-items-center rounded-2xl border border-[#e7ebf2] bg-white text-[#60708a] shadow-sm transition hover:bg-[#fff0ea] hover:text-[#ed633f]"
              aria-label="Expand sidebar"
            >
              <ChevronRight className="size-4" />
            </button>
          )}

          {!collapsed && (
            <div className="px-4 pt-4">
              <label className="flex items-center gap-2 rounded-2xl border border-[#e4e9f1] bg-[#f8fafc] px-3 py-2.5 text-sm text-[#8a97aa]">
                <Search className="size-4" />
                <span>Search...</span>
              </label>

              <div className="mt-4 flex items-center gap-3 rounded-2xl border border-[#e4e9f1] bg-white px-3 py-3 shadow-sm">
                <Building2 className="size-4 shrink-0 text-[#ed633f]" />
                <BusinessSwitcher
                  businesses={businesses}
                  activeId={activeId}
                  className="text-[#172033]"
                />
                <ChevronRight className="size-3.5 rotate-90 text-[#9aa6b8]" />
              </div>
            </div>
          )}

          <div className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
            <nav className="space-y-1.5">
              {primary.map(([label, href, Icon]) => (
                <Link key={href} href={href} className={desktopLinkClass(href)} title={label}>
                  <Icon className="size-4 shrink-0" />
                  {!collapsed && <span className="truncate">{label}</span>}
                </Link>
              ))}
            </nav>

            {!collapsed && (
              <p className="mb-2 mt-7 px-3 text-[10px] font-black uppercase tracking-[0.18em] text-[#a1adbf]">
                Manage
              </p>
            )}
            <nav className={cn("space-y-1.5", collapsed ? "mt-5" : "")}>
              {manage.map(([label, href, Icon]) => (
                <Link key={href} href={href} className={desktopLinkClass(href)} title={label}>
                  <Icon className="size-4 shrink-0" />
                  {!collapsed && <span className="truncate">{label}</span>}
                </Link>
              ))}
            </nav>
          </div>

          <div className={cn("border-t border-[#edf0f5]", collapsed ? "p-3" : "p-4")}>
            <div className={cn("flex items-center", collapsed ? "justify-center" : "gap-3")}>
              <div className="relative">
                <div className="grid size-10 place-items-center rounded-full bg-[#eef3fb] text-sm font-bold text-[#34445f]">
                  {initials || "B"}
                </div>
                <span className="absolute bottom-0 right-0 size-2.5 rounded-full border-2 border-white bg-emerald-500" />
              </div>
              {!collapsed && (
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold">{displayName}</p>
                  <p className="truncate text-xs text-[#7b8799]">
                    {user?.primaryEmailAddress?.emailAddress ?? "Workspace owner"}
                  </p>
                </div>
              )}
            </div>

            <div className={cn("mt-3 flex", collapsed ? "justify-center" : "gap-2")}>
              {!collapsed && (
                <Link
                  href="/support"
                  className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl border border-[#e7ebf2] px-3 py-2 text-xs font-bold text-[#60708a] transition hover:bg-[#f5f7fb] hover:text-[#172033]"
                >
                  <HelpCircle className="size-3.5" />
                  Support
                </Link>
              )}
              <SignOutButton>
                <button
                  type="button"
                  className={cn(
                    "inline-flex items-center justify-center gap-2 rounded-xl px-3 py-2 text-xs font-bold text-red-600 transition hover:bg-red-50",
                    collapsed ? "size-10" : "border border-red-100",
                  )}
                  title="Logout"
                >
                  <LogOut className="size-4" />
                  {!collapsed && "Logout"}
                </button>
              </SignOutButton>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}

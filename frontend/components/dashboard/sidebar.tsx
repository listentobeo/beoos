"use client";

import { UserButton } from "@clerk/nextjs";
import {
  BarChart3,
  Building2,
  ClipboardList,
  FileText,
  FilePenLine,
  Inbox,
  MessageCircleMore,
  Settings,
  ShieldAlert,
  Sparkles,
  Tags,
  UsersRound,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BusinessSwitcher } from "@/components/dashboard/business-switcher";
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
  ["Business settings", "/dashboard/settings", Settings],
] as const;

export function Sidebar({ businesses, activeId }: { businesses: Business[]; activeId: string | null }) {
  const pathname = usePathname();
  const allLinks = [...primary, ...manage];

  function isActive(href: string) {
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  function linkClass(href: string, mobile = false) {
    const active = isActive(href);
    if (mobile) {
      return `flex shrink-0 items-center gap-2 rounded-xl px-3 py-2 text-xs transition ${
        active
          ? "bg-white text-[#171b23]"
          : "bg-white/[0.06] text-white/70 hover:bg-white/[0.1] hover:text-white"
      }`;
    }
    return `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition ${
      active ? "bg-white text-[#171b23]" : "text-white/65 hover:bg-white/[0.06] hover:text-white"
    }`;
  }

  return (
    <>
      <div className="fixed inset-x-0 top-0 z-30 border-b border-white/10 bg-[#101827] px-4 py-3 text-white lg:hidden">
        <div className="flex items-center gap-3">
          <div className="grid size-9 place-items-center rounded-xl bg-[#ed633f] text-sm font-black tracking-tight">B</div>
          <div className="min-w-0">
            <p className="text-sm font-bold tracking-tight">BeoOS</p>
            <p className="truncate text-[10px] text-white/45">Creative business intelligence</p>
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
            <Link key={href} href={href} className={linkClass(href, true)}>
              <Icon className="size-3.5" />
              {label}
            </Link>
          ))}
        </nav>
      </div>

      <aside className="fixed inset-y-0 left-0 z-20 hidden w-[264px] flex-col overflow-y-auto bg-[#101827] px-4 py-5 text-white lg:flex">
        <div className="flex items-center gap-3 px-2">
          <div className="grid size-10 place-items-center rounded-xl bg-[#ed633f] font-black tracking-tight">B</div>
          <div>
            <p className="text-base font-bold tracking-tight">BeoOS</p>
            <p className="text-[11px] text-white/45">Creative business intelligence</p>
          </div>
          <div className="ml-auto" aria-label="Account menu">
            <UserButton />
          </div>
        </div>

        <button className="mt-7 flex w-full items-center gap-3 rounded-xl border border-white/10 bg-white/[0.06] px-3 py-3 text-left">
          <Building2 className="size-4 text-[#f69a7e]" />
          <BusinessSwitcher businesses={businesses} activeId={activeId} />
          <span className="text-white/35">⌄</span>
        </button>

        <nav className="mt-6 space-y-1">
          {primary.map(([label, href, Icon]) => (
            <Link key={href} href={href} className={linkClass(href)}>
              <Icon className="size-4" />
              {label}
            </Link>
          ))}
        </nav>

        <p className="mb-2 mt-7 px-3 text-[10px] font-bold uppercase tracking-[0.18em] text-white/30">Manage</p>
        <nav className="space-y-1">
          {manage.map(([label, href, Icon]) => (
            <Link key={href} href={href} className={linkClass(href)}>
              <Icon className="size-4" />
              {label}
            </Link>
          ))}
        </nav>

        <div className="mt-auto rounded-2xl border border-white/10 bg-white/[0.05] p-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-white/85">
            <Sparkles className="size-4 text-[#f69a7e]" /> AI email assistant
          </div>
          <p className="mt-1.5 text-[11px] leading-relaxed text-white/45">Policy-gated replies are active.</p>
        </div>
      </aside>
    </>
  );
}

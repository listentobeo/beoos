import { ArrowUpRight, Building2, CircleAlert, MessageCircleMore } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { Thread } from "@/lib/api";

const categoryStyles: Record<string, string> = {
  portrait: "bg-violet-50 text-violet-700",
  mural: "bg-sky-50 text-sky-700",
  live_painting: "bg-amber-50 text-amber-700",
  sfx: "bg-fuchsia-50 text-fuchsia-700",
  art_school: "bg-emerald-50 text-emerald-700",
  existing_client: "bg-blue-50 text-blue-700",
  corporate: "bg-slate-100 text-slate-700",
  urgent: "bg-red-50 text-red-700",
  spam: "bg-zinc-100 text-zinc-500",
  general: "bg-orange-50 text-orange-700",
};

function relativeTime(dateString: string) {
  const seconds = Math.round((new Date(dateString).getTime() - Date.now()) / 1000);
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  if (Math.abs(seconds) < 60) return formatter.format(seconds, "second");
  const minutes = Math.round(seconds / 60);
  if (Math.abs(minutes) < 60) return formatter.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return formatter.format(hours, "hour");
  return formatter.format(Math.round(hours / 24), "day");
}

export function InboxTable({ threads }: { threads: Thread[] }) {
  if (threads.length === 0) {
    return (
      <div className="grid min-h-72 place-items-center px-6 text-center">
        <div>
          <div className="mx-auto grid size-12 place-items-center rounded-2xl bg-[#fff0ea] text-[#ed633f]">
            <MessageCircleMore className="size-5" />
          </div>
          <h3 className="mt-4 text-sm font-bold">Your inbox is ready</h3>
          <p className="mt-1 max-w-sm text-sm leading-relaxed text-[#727771]">
            Connect Zoho Mail in Business Settings. New messages will be classified and acknowledged here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="divide-y">
      {threads.map((thread) => (
        <button key={thread.id} className="group grid w-full grid-cols-[32px_1fr_auto] gap-3 px-5 py-4 text-left transition hover:bg-[#fbfaf7] md:grid-cols-[32px_180px_1fr_150px_100px] md:items-center">
          <span className={`mt-1 size-2 rounded-full md:mt-0 ${thread.unread_count ? "bg-[#ed633f]" : "bg-[#d8d8d2]"}`} />
          <div className="hidden min-w-0 md:block">
            <p className="truncate text-sm font-semibold">{thread.contact_name || thread.contact_email || "Unknown sender"}</p>
            <p className="truncate text-xs text-[#8a8e88]">{thread.contact_email}</p>
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="truncate text-sm font-semibold text-[#262a31]">{thread.subject}</p>
              {thread.is_professional && <Building2 className="size-3.5 shrink-0 text-[#7f8580]" />}
              {thread.priority >= 100 && <CircleAlert className="size-3.5 shrink-0 text-red-500" />}
            </div>
            <p className="mt-1 truncate text-xs text-[#818680] md:hidden">{thread.contact_name || thread.contact_email}</p>
            <div className="mt-2 flex gap-2 md:hidden">
              <Badge className={categoryStyles[thread.category] ?? categoryStyles.general}>{thread.category.replaceAll("_", " ")}</Badge>
            </div>
          </div>
          <div className="hidden md:block">
            <Badge className={categoryStyles[thread.category] ?? categoryStyles.general}>{thread.category.replaceAll("_", " ")}</Badge>
          </div>
          <div className="flex items-center justify-end gap-2 text-xs text-[#8a8e88]">
            <span>{relativeTime(thread.latest_message_at)}</span>
            <ArrowUpRight className="size-4 opacity-0 transition group-hover:opacity-100" />
          </div>
        </button>
      ))}
    </div>
  );
}


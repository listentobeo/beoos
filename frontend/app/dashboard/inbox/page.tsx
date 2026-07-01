import { Bell, FilePenLine, Inbox, MessageCircleMore, Search, ShieldAlert, UsersRound } from "lucide-react";
import { InboxTable } from "@/components/dashboard/inbox-table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { activeBusiness, beoApi, type InboxStats, type Thread } from "@/lib/api";

const emptyStats: InboxStats = { unread: 0, needs_approval: 0, urgent: 0, routed_whatsapp: 0, existing_clients: 0 };

export const metadata = { title: "Inbox" };

export default async function InboxPage() {
  let stats = emptyStats;
  let threads: Thread[] = [];
  let connected = true;
  let businessName = "Beo Art Studio";

  try {
    const business = await activeBusiness();
    if (!business) connected = false;
    else {
      businessName = business.name;
      [stats, threads] = await Promise.all([beoApi.stats(business.id), beoApi.threads(business.id)]);
    }
  } catch {
    connected = false;
  }

  const statCards = [
    ["Unread", stats.unread, Inbox, "text-[#ed633f] bg-[#fff0ea]"],
    ["Needs approval", stats.needs_approval, FilePenLine, "text-violet-700 bg-violet-50"],
    ["Urgent", stats.urgent, ShieldAlert, "text-red-600 bg-red-50"],
    ["WhatsApp", stats.routed_whatsapp, MessageCircleMore, "text-emerald-700 bg-emerald-50"],
    ["Existing clients", stats.existing_clients, UsersRound, "text-blue-700 bg-blue-50"],
  ] as const;

  return (
    <div className="mx-auto max-w-[1480px] px-5 py-5 md:px-8 md:py-8">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#90948f]">{businessName}</p>
          <h1 className="mt-1 text-3xl font-bold tracking-[-0.035em] text-[#171b23]">Good morning, Benjamin.</h1>
          <p className="mt-1 text-sm text-[#747973]">Here’s what needs your attention today.</p>
        </div>
        <Button variant="outline" size="icon" aria-label="Notifications"><Bell className="size-4" /></Button>
      </header>

      {!connected && (
        <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          BeoOS is waiting for its Clerk and backend environment variables. Your dashboard will populate after setup.
        </div>
      )}

      <section className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {statCards.map(([label, value, Icon, style]) => (
          <Card key={label} className="flex items-center gap-4 p-4">
            <div className={`grid size-10 shrink-0 place-items-center rounded-xl ${style}`}><Icon className="size-4" /></div>
            <div>
              <p className="text-2xl font-bold tracking-tight">{value}</p>
              <p className="text-xs text-[#858a84]">{label}</p>
            </div>
          </Card>
        ))}
      </section>

      <Card className="mt-6 overflow-hidden">
        <div className="flex flex-col gap-4 border-b px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-bold tracking-tight">Unified inbox</h2>
            <p className="mt-0.5 text-xs text-[#858a84]">Zoho Mail, classified by BeoOS</p>
          </div>
          <div className="flex items-center gap-2 rounded-xl border bg-[#faf9f6] px-3 py-2 text-sm text-[#777c76] sm:w-64">
            <Search className="size-4" />
            <span>Search conversations</span>
          </div>
        </div>
        <InboxTable threads={threads} />
      </Card>
    </div>
  );
}

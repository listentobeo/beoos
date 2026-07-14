import { Bell, FilePenLine, Inbox, MessageCircleMore, ShieldAlert, UsersRound } from "lucide-react";
import Link from "next/link";
import { ConversationSearch } from "@/components/dashboard/conversation-search";
import { InboxTable } from "@/components/dashboard/inbox-table";
import { SyncMailboxButton } from "@/components/dashboard/sync-mailbox-button";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { activeBusiness, beoApi, type InboxStats, type MailboxStatus, type Thread } from "@/lib/api";

const emptyStats: InboxStats = {
  unread: 0,
  needs_approval: 0,
  urgent: 0,
  routed_whatsapp: 0,
  existing_clients: 0,
};

export const metadata = { title: "Inbox" };

export default async function InboxPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const query = ((await searchParams).q ?? "").trim();
  let stats = emptyStats;
  let threads: Thread[] = [];
  let mailbox: MailboxStatus | null = null;
  let connected = true;
  let businessId: string | null = null;
  let businessName = "Beo Art Studio";

  try {
    const business = await activeBusiness();
    if (!business) connected = false;
    else {
      const summary = await beoApi.dashboard(business.id, query || undefined);
      businessId = summary.business.id;
      businessName = summary.business.name;
      stats = summary.inbox_stats;
      threads = summary.threads;
      mailbox = summary.mailbox;
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
  const providerLabel =
    mailbox?.provider === "gmail"
      ? "Gmail status"
      : mailbox?.provider === "zoho"
        ? "Zoho Mail status"
        : "Email status";
  const connectedCopy = mailbox?.connected
    ? `Connected to ${mailbox.email_address}`
    : "Not connected yet";
  const autoSyncCopy = mailbox?.auto_sync_enabled
    ? `Auto-sync is active every ${mailbox.auto_sync_interval_seconds || 60} seconds.`
    : "Auto-sync is disabled; use Sync now or enable mailbox auto-sync on the backend.";

  return (
    <div className="mx-auto max-w-[1480px] px-4 py-5 sm:px-5 md:px-8 md:py-8">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#90948f]">{businessName}</p>
          <h1 className="mt-1 text-2xl font-bold tracking-[-0.035em] text-[#171b23] sm:text-3xl">Good morning, Benjamin.</h1>
          <p className="mt-1 text-sm text-[#747973]">Here&apos;s what needs your attention today.</p>
        </div>
        <Button asChild variant="outline" size="icon" aria-label="Notifications">
          <Link href="/dashboard/settings#notifications"><Bell className="size-4" /></Link>
        </Button>
      </header>

      {!connected && (
        <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          BeoOS could not load your business data. Confirm the latest Railway deployment completed its initial business setup.
        </div>
      )}

      {connected && (
        <Card className="mt-6 p-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#90948f]">{providerLabel}</p>
              <h2 className="mt-1 text-base font-bold">
                {connectedCopy}
              </h2>
              <p className="mt-1 text-sm text-[#747973]">
                {mailbox?.last_synced_at
                  ? `Last synced ${new Date(mailbox.last_synced_at).toLocaleString()} · ${mailbox.message_count} messages imported`
                  : mailbox?.connected
                    ? `Connected, but no sync has completed yet. ${autoSyncCopy}`
                    : "Connect Zoho Mail or Gmail in Business Settings before BeoOS can pull messages."}
              </p>
              {mailbox?.connected && <p className="mt-1 text-xs text-emerald-700">{autoSyncCopy}</p>}
            </div>
            {businessId && mailbox?.connected && <SyncMailboxButton businessId={businessId} />}
          </div>
        </Card>
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
            <p className="mt-0.5 text-xs text-[#858a84]">Zoho Mail, website forms, and WhatsApp, classified by BeoOS</p>
            {query && <p className="mt-1 text-xs font-medium text-[#ed633f]">Showing results for “{query}”</p>}
          </div>
          <ConversationSearch initialQuery={query} />
        </div>
        <InboxTable
          threads={threads}
          mailboxConnected={Boolean(mailbox?.connected)}
          emptyMessage={query ? `No conversations matched “${query}”. Try a sender, subject, or service keyword.` : undefined}
        />
      </Card>
    </div>
  );
}

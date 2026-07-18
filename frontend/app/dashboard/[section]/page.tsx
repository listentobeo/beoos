import { Archive, Construction, MessageCircleMore, ShieldAlert, ShieldX, UsersRound } from "lucide-react";
import { ClientDirectory } from "@/components/dashboard/client-directory";
import { InfiniteThreadList } from "@/components/dashboard/infinite-thread-list";
import { Card } from "@/components/ui/card";
import { activeBusiness, beoApi, type ClientContact, type Thread } from "@/lib/api";

type ThreadFilters = { category?: string; status?: string; provider?: string };

const sectionConfig: Record<
  string,
  {
    title: string;
    eyebrow: string;
    description: string;
    filters: ThreadFilters;
    empty: string;
    icon: typeof MessageCircleMore;
  }
> = {
  urgent: {
    title: "Urgent conversations",
    eyebrow: "Inbox priority",
    description: "High-priority conversations BeoOS believes need fast owner attention.",
    filters: { category: "urgent" },
    empty: "No urgent conversations right now. When a message looks time-sensitive, it will appear here.",
    icon: ShieldAlert,
  },
  clients: {
    title: "Existing clients",
    eyebrow: "Client history",
    description: "Known contacts and repeat clients, grouped from your connected email, forms, and WhatsApp inbox.",
    filters: { category: "existing_client" },
    empty: "No existing client conversations yet. Repeat clients will appear here after BeoOS identifies the contact.",
    icon: UsersRound,
  },
  whatsapp: {
    title: "WhatsApp inbox",
    eyebrow: "Channel view",
    description: "WhatsApp conversations captured through your connected Meta Cloud API number.",
    filters: { provider: "whatsapp" },
    empty: "No WhatsApp conversations yet. Send a message to the connected number after webhook setup.",
    icon: MessageCircleMore,
  },
  spam: {
    title: "Spam and noise",
    eyebrow: "Inbox hygiene",
    description: "Verification codes, bounces, obvious system notifications, and manually discarded noise live here.",
    filters: { category: "spam" },
    empty: "Spam and noise is empty. BeoOS will move obvious codes and irrelevant system messages here.",
    icon: ShieldX,
  },
  archived: {
    title: "Archived conversations",
    eyebrow: "Closed threads",
    description: "Handled conversations removed from the active inbox without deleting their history.",
    filters: { status: "closed" },
    empty: "No archived conversations yet. Archive handled threads from the inbox detail page.",
    icon: Archive,
  },
};

export default async function DashboardSectionPage({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  const config = sectionConfig[section];
  let businessId: string | null = null;
  let threads: Thread[] | null = null;
  let clients: ClientContact[] = [];

  if (config) {
    try {
      const business = await activeBusiness();
      businessId = business?.id ?? null;
      if (business && section === "clients") {
        clients = await beoApi.clients(business.id);
        threads = [];
      } else {
        threads = business ? await beoApi.threads(business.id, config.filters) : [];
      }
    } catch {
      threads = [];
    }
  }

  if (!config) {
    return (
      <div className="mx-auto max-w-5xl px-5 py-8 md:px-8">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#90948f]">
          BeoOS workspace
        </p>
        <h1 className="mt-1 text-3xl font-bold capitalize tracking-[-0.035em]">{section.replaceAll("-", " ")}</h1>
        <Card className="mt-7 grid min-h-72 place-items-center p-8 text-center">
          <div>
            <Construction className="mx-auto size-8 text-[#ed633f]" />
            <p className="mt-4 font-bold">This workspace is ready for the next workflow upgrade.</p>
            <p className="mt-1 text-sm text-[#777c76]">Live data will populate it after its integration is connected.</p>
          </div>
        </Card>
      </div>
    );
  }

  const Icon = config.icon;

  return (
    <div className="mx-auto max-w-6xl px-5 py-8 md:px-8">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#90948f]">
        {config.eyebrow}
      </p>
      <div className="mt-1 flex items-center gap-3">
        <span className="grid size-10 place-items-center rounded-2xl bg-[#fff0ea] text-[#ed633f]">
          <Icon className="size-5" />
        </span>
        <h1 className="text-3xl font-bold tracking-[-0.035em]">{config.title}</h1>
      </div>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-[#747973]">{config.description}</p>

      <Card className="mt-7 overflow-hidden">
        {businessId && section === "clients" ? (
          <ClientDirectory businessId={businessId} clients={clients} />
        ) : businessId && threads ? (
          <InfiniteThreadList
            businessId={businessId}
            initialThreads={threads}
            filters={config.filters}
            emptyMessage={config.empty}
          />
        ) : (
          <div className="grid min-h-72 place-items-center p-8 text-center">
            <p className="text-sm text-[#777c76]">Create a business first to activate this section.</p>
          </div>
        )}
      </Card>
    </div>
  );
}

import {
  ArrowUpRight,
  BarChart3,
  Bot,
  Compass,
  Lightbulb,
  Megaphone,
  MousePointerClick,
  Search,
} from "lucide-react";
import Link from "next/link";
import { MarketingImportForm } from "@/components/dashboard/marketing-import-form";
import { SetupGuide } from "@/components/dashboard/setup-guide";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  activeBusiness,
  beoApi,
  type MarketingActionItem,
  type MarketingContentCluster,
  type MarketingPageOpportunity,
  type MarketingQueryOpportunity,
  type MarketingSummary,
} from "@/lib/api";

export const metadata = { title: "Marketing intelligence" };

function percent(value: number | string | null | undefined) {
  const number = typeof value === "string" ? Number(value) : Number(value ?? 0);
  return `${(number * 100).toFixed(number > 0 && number < 0.01 ? 2 : 1)}%`;
}

function sourceLabel(source: string) {
  return source.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function total(summary: MarketingSummary, key: "rows" | "impressions" | "clicks" | "sessions" | "leads") {
  return summary.totals.reduce((sum, item) => sum + item[key], 0);
}

function EmptyMarketing() {
  return (
    <Card className="grid min-h-72 place-items-center p-8 text-center">
      <div>
        <Megaphone className="mx-auto size-10 text-[#ed633f]" />
        <h2 className="mt-4 text-xl font-bold tracking-[-0.03em]">
          Marketing intelligence is ready for signal data
        </h2>
        <p className="mt-2 max-w-xl text-sm leading-6 text-[#747973]">
          Import Search Console, Blogger, Microsoft Clarity, or website/form metrics. BeoOS will
          turn them into query opportunities, content clusters, and precise next actions for this
          business only.
        </p>
      </div>
    </Card>
  );
}

function SignalCard({
  label,
  value,
  helper,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  helper: string;
  icon: typeof BarChart3;
}) {
  return (
    <Card className="flex items-center gap-4 p-4">
      <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-orange-50 text-orange-700">
        <Icon className="size-5" />
      </div>
      <div>
        <p className="text-2xl font-bold tracking-[-0.03em]">{value}</p>
        <p className="text-sm font-semibold text-[#30343a]">{label}</p>
        <p className="text-xs text-[#747973]">{helper}</p>
      </div>
    </Card>
  );
}

function ActionPanel({ actions }: { actions: MarketingActionItem[] }) {
  const priorityClass = {
    high: "bg-red-50 text-red-700",
    medium: "bg-amber-50 text-amber-700",
    low: "bg-slate-100 text-slate-700",
  };
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-bold">Priority marketing actions</h2>
          <p className="mt-1 text-sm leading-6 text-[#747973]">
            The punch list BeoOS would hand to a marketer before writing or publishing anything.
          </p>
        </div>
        <Badge className="bg-[#111827] text-white">{actions.length} actions</Badge>
      </div>
      <div className="mt-5 space-y-3">
        {actions.length === 0 ? (
          <p className="rounded-xl bg-[#f7f6f2] p-4 text-sm text-[#747973]">
            No action items yet. Import more signal data first.
          </p>
        ) : (
          actions.map((item, index) => (
            <div key={`${item.label}-${index}`} className="rounded-2xl border p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge className={priorityClass[item.priority]}>{item.priority}</Badge>
                <Badge className="bg-[#f7f4ef] text-[#6c6259]">{sourceLabel(item.source)}</Badge>
              </div>
              <h3 className="mt-3 font-bold">{item.label}</h3>
              <p className="mt-1 text-sm leading-6 text-[#747973]">{item.reason}</p>
              <p className="mt-3 rounded-xl bg-[#fff8f4] p-3 text-sm font-medium leading-6 text-[#593427]">
                {item.recommended_action}
              </p>
              {item.page_url && (
                <Link
                  href={item.page_url}
                  className="mt-3 inline-flex items-center gap-1 text-xs font-bold text-[#ed633f]"
                  target="_blank"
                >
                  Open page <ArrowUpRight className="size-3" />
                </Link>
              )}
            </div>
          ))
        )}
      </div>
    </Card>
  );
}

function QueryPanel({ queries }: { queries: MarketingQueryOpportunity[] }) {
  return (
    <Card className="p-5">
      <h2 className="font-bold">Search query opportunities</h2>
      <p className="mt-1 text-sm leading-6 text-[#747973]">
        Queries with visibility but weak clicks or rankings within striking distance.
      </p>
      <div className="mt-5 space-y-3">
        {queries.length === 0 ? (
          <p className="rounded-xl bg-[#f7f6f2] p-4 text-sm text-[#747973]">No query gaps yet.</p>
        ) : (
          queries.map((item) => (
            <div key={`${item.query}-${item.page_url}`} className="rounded-2xl border p-4">
              <p className="font-bold">“{item.query}”</p>
              <div className="mt-2 flex flex-wrap gap-2 text-xs text-[#747973]">
                <Badge className="bg-blue-50 text-blue-700">{item.impressions} impressions</Badge>
                <Badge className="bg-green-50 text-green-700">{item.clicks} clicks</Badge>
                <Badge className="bg-orange-50 text-orange-700">{percent(item.ctr)} CTR</Badge>
                {item.average_position && (
                  <Badge className="bg-violet-50 text-violet-700">
                    pos. {item.average_position.toFixed(1)}
                  </Badge>
                )}
              </div>
              <p className="mt-3 text-sm leading-6 text-[#5f655f]">{item.recommendation}</p>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}

function ClusterPanel({ clusters }: { clusters: MarketingContentCluster[] }) {
  return (
    <Card className="p-5">
      <h2 className="font-bold">Content clusters</h2>
      <p className="mt-1 text-sm leading-6 text-[#747973]">
        Topic groups BeoOS sees from imported search, blog, and behavior signals.
      </p>
      <div className="mt-5 grid gap-3 md:grid-cols-2">
        {clusters.length === 0 ? (
          <p className="rounded-xl bg-[#f7f6f2] p-4 text-sm text-[#747973] md:col-span-2">
            No cluster pattern yet.
          </p>
        ) : (
          clusters.map((cluster) => (
            <div key={cluster.topic} className="rounded-2xl border p-4">
              <p className="font-bold">{cluster.topic}</p>
              <p className="mt-1 text-xs text-[#747973]">
                {cluster.impressions} impressions · {cluster.clicks} clicks
              </p>
              {cluster.queries.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {cluster.queries.slice(0, 3).map((query) => (
                    <Badge key={query} className="bg-[#f7f4ef] text-[#6c6259]">
                      {query}
                    </Badge>
                  ))}
                </div>
              )}
              <p className="mt-3 text-sm leading-6 text-[#5f655f]">{cluster.recommended_angle}</p>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}

function PagePanel({ pages }: { pages: MarketingPageOpportunity[] }) {
  return (
    <Card className="p-5">
      <h2 className="font-bold">Page opportunities</h2>
      <p className="mt-1 text-sm leading-6 text-[#747973]">
        Landing pages, service pages, blog posts, and form pages ranked by opportunity.
      </p>
      <div className="mt-5 overflow-hidden rounded-2xl border">
        {pages.length === 0 ? (
          <p className="p-4 text-sm text-[#747973]">No page metrics yet.</p>
        ) : (
          <div className="divide-y">
            {pages.map((page) => (
              <div key={`${page.page_url}-${page.title}`} className="grid gap-3 p-4 lg:grid-cols-[1fr_160px_120px] lg:items-center">
                <div>
                  <p className="font-bold">{page.title || page.page_url || "Untitled page"}</p>
                  <p className="mt-1 line-clamp-1 text-xs text-[#747973]">{page.page_url}</p>
                  <p className="mt-2 text-sm leading-6 text-[#5f655f]">{page.recommendation}</p>
                </div>
                <div className="flex gap-2 lg:block lg:space-y-2">
                  <Badge className="bg-blue-50 text-blue-700">{page.impressions} impressions</Badge>
                  <Badge className="bg-emerald-50 text-emerald-700">{page.sessions} sessions</Badge>
                </div>
                <div className="text-sm font-bold text-[#30343a]">
                  {percent(page.ctr)} CTR
                  {page.average_position ? (
                    <p className="text-xs font-medium text-[#747973]">position {page.average_position}</p>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

function MarketingContent({ businessName, summary, businessId }: { businessName: string; summary: MarketingSummary; businessId: string }) {
  const hasData = total(summary, "rows") > 0;
  return (
    <div className="mx-auto max-w-[1500px] px-4 py-8 sm:px-5 md:px-8">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#90948f]">
        {businessName}
      </p>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="mt-1 text-2xl font-bold tracking-[-0.035em] sm:text-3xl">
            Marketing intelligence
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[#747973]">
            BeoOS combines Search Console, Blogger, Clarity, and website/form signals into precise
            content clusters, page fixes, and growth actions per tenant.
          </p>
        </div>
        <Badge className="bg-[#111827] text-white">Last {summary.window_days} days</Badge>
      </div>

      <section className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <SignalCard icon={BarChart3} label="Imported rows" value={total(summary, "rows")} helper="Signal records" />
        <SignalCard icon={Search} label="Impressions" value={total(summary, "impressions")} helper="Search visibility" />
        <SignalCard icon={MousePointerClick} label="Clicks" value={total(summary, "clicks")} helper="Search/blog visits" />
        <SignalCard icon={Compass} label="Sessions" value={total(summary, "sessions")} helper="Behavior signals" />
        <SignalCard icon={Bot} label="Leads" value={total(summary, "leads")} helper="Imported conversion signal" />
      </section>

      <section className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        {summary.totals.map((item) => (
          <Card key={item.source} className="p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#90948f]">
              {sourceLabel(item.source)}
            </p>
            <p className="mt-2 text-2xl font-bold">{item.rows}</p>
            <p className="text-xs text-[#747973]">
              {item.impressions} impressions · {item.sessions} sessions
            </p>
          </Card>
        ))}
      </section>

      <div className="mt-7">{hasData ? <ActionPanel actions={summary.action_items} /> : <EmptyMarketing />}</div>

      <section className="mt-5 grid gap-5 xl:grid-cols-2">
        <QueryPanel queries={summary.query_opportunities} />
        <ClusterPanel clusters={summary.content_clusters} />
      </section>

      <section className="mt-5">
        <PagePanel pages={summary.top_pages} />
      </section>

      <section className="mt-5">
        <MarketingImportForm businessId={businessId} />
      </section>

      <div className="mt-5 rounded-2xl border bg-[#fffaf7] p-5">
        <div className="flex items-start gap-3">
          <Lightbulb className="mt-0.5 size-5 shrink-0 text-[#ed633f]" />
          <p className="text-sm leading-6 text-[#5f655f]">
            Precision rule: service pages remain authority pages, blogs support education, Clarity
            explains user friction, and Search Console tells BeoOS what people are already asking.
            Publishing automation should only come after these signals are clean.
          </p>
        </div>
      </div>
    </div>
  );
}

export default async function MarketingPage() {
  try {
    const business = await activeBusiness();
    if (!business) {
      return (
        <div className="mx-auto max-w-5xl px-4 py-8 sm:px-5 md:px-8">
          <SetupGuide compact />
        </div>
      );
    }
    const summary = await beoApi.marketing(business.id);
    return <MarketingContent businessName={business.name} summary={summary} businessId={business.id} />;
  } catch {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-5 md:px-8">
        <Card className="p-8">
          <div className="flex items-start gap-4">
            <div className="grid size-11 place-items-center rounded-2xl bg-red-50 text-red-700">
              <Megaphone className="size-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold">Marketing intelligence could not load</h1>
              <p className="mt-2 text-sm leading-6 text-[#747973]">
                Confirm the backend deployment is up to date and that your user has access to the
                selected business.
              </p>
            </div>
          </div>
        </Card>
      </div>
    );
  }
}

import {
  Activity,
  ArrowUpRight,
  BarChart3,
  CalendarClock,
  CheckCircle2,
  CircleDollarSign,
  Inbox,
  MessageSquareText,
  ShieldAlert,
  TrendingUp,
  UsersRound,
} from "lucide-react";
import Link from "next/link";
import type { ComponentType } from "react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { activeBusiness, beoApi, type AnalyticsBucket, type AnalyticsSummary } from "@/lib/api";

export const metadata = { title: "Analytics" };

const bucketStyles: Record<string, string> = {
  whatsapp: "bg-emerald-50 text-emerald-700",
  zoho: "bg-orange-50 text-orange-700",
  gmail: "bg-blue-50 text-blue-700",
  website_form: "bg-violet-50 text-violet-700",
  hot: "bg-red-50 text-red-700",
  warm: "bg-amber-50 text-amber-700",
  cold: "bg-slate-100 text-slate-700",
  accepted: "bg-green-50 text-green-700",
  won: "bg-green-50 text-green-700",
  needs_approval: "bg-orange-50 text-orange-700",
};

function money(value: string | number | null | undefined, currency = "NGN") {
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
}

function dateTime(value: string) {
  return new Intl.DateTimeFormat("en-NG", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function maxCount(items: AnalyticsBucket[]) {
  return Math.max(...items.map((item) => item.count), 1);
}

function percent(value: number) {
  return `${value.toFixed(value % 1 ? 1 : 0)}%`;
}

function EmptyState() {
  return (
    <Card className="grid min-h-72 place-items-center p-8 text-center">
      <div>
        <BarChart3 className="mx-auto size-9 text-[#ed633f]" />
        <h2 className="mt-4 text-lg font-bold">Analytics will light up as data enters BeoOS</h2>
        <p className="mt-2 max-w-md text-sm leading-6 text-[#747973]">
          Connect email, WhatsApp, website forms, CRM leads, and quotations. BeoOS then turns those
          conversations into business intelligence for this tenant only.
        </p>
        <Link
          href="/dashboard/settings"
          className="mt-5 inline-flex rounded-xl bg-[#ed633f] px-4 py-2 text-sm font-bold text-white"
        >
          Open business settings
        </Link>
      </div>
    </Card>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  helper,
  tone = "orange",
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  helper: string;
  tone?: "orange" | "blue" | "green" | "violet" | "red" | "slate";
}) {
  const tones = {
    orange: "bg-orange-50 text-orange-700",
    blue: "bg-blue-50 text-blue-700",
    green: "bg-green-50 text-green-700",
    violet: "bg-violet-50 text-violet-700",
    red: "bg-red-50 text-red-700",
    slate: "bg-slate-100 text-slate-700",
  };
  return (
    <Card className="flex items-center gap-4 p-4">
      <div className={`grid size-11 shrink-0 place-items-center rounded-2xl ${tones[tone]}`}>
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

function BucketPanel({
  title,
  description,
  items,
  showValue = false,
}: {
  title: string;
  description: string;
  items: AnalyticsBucket[];
  showValue?: boolean;
}) {
  const max = maxCount(items);
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-bold">{title}</h2>
          <p className="mt-1 text-xs leading-5 text-[#747973]">{description}</p>
        </div>
        <Badge className="bg-[#f7f4ef] text-[#6c6259]">{items.length} groups</Badge>
      </div>
      <div className="mt-5 space-y-4">
        {items.length === 0 ? (
          <p className="rounded-xl bg-[#f7f6f2] p-4 text-sm text-[#747973]">No data yet.</p>
        ) : (
          items.map((item) => (
            <div key={item.key}>
              <div className="mb-2 flex items-center justify-between gap-3 text-sm">
                <div className="flex items-center gap-2">
                  <Badge className={bucketStyles[item.key] ?? "bg-slate-100 text-slate-700"}>
                    {item.label}
                  </Badge>
                  {showValue && item.value && (
                    <span className="text-xs font-semibold text-[#747973]">
                      {money(item.value)}
                    </span>
                  )}
                </div>
                <span className="font-bold">{item.count}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-[#f0eee9]">
                <div
                  className="h-full rounded-full bg-[#ed633f]"
                  style={{ width: `${Math.max(6, (item.count / max) * 100)}%` }}
                />
              </div>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}

function AnalyticsContent({
  businessName,
  summary,
}: {
  businessName: string;
  summary: AnalyticsSummary;
}) {
  const hasData =
    summary.totals.conversations ||
    summary.totals.leads ||
    summary.totals.quotes ||
    summary.recent_activity.length;

  return (
    <div className="mx-auto max-w-[1500px] px-4 py-8 sm:px-5 md:px-8">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#90948f]">
        {businessName}
      </p>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="mt-1 text-2xl font-bold tracking-[-0.035em] sm:text-3xl">
            Business intelligence
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[#747973]">
            Module 4.1 connects inbox activity, WhatsApp, CRM, quotations, approvals, and follow-ups
            into one tenant-scoped operating dashboard.
          </p>
        </div>
        <Badge className="bg-[#111827] text-white">Last {summary.window_days} days</Badge>
      </div>

      {!hasData ? (
        <div className="mt-7">
          <EmptyState />
        </div>
      ) : (
        <>
          <section className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              icon={Inbox}
              label="Conversations"
              value={summary.totals.conversations}
              helper="Active inbox threads"
              tone="orange"
            />
            <MetricCard
              icon={MessageSquareText}
              label="Inbound messages"
              value={summary.totals.inbound_messages}
              helper="Email, forms, WhatsApp"
              tone="blue"
            />
            <MetricCard
              icon={UsersRound}
              label="New leads"
              value={summary.totals.leads}
              helper="AI/manual CRM entries"
              tone="green"
            />
            <MetricCard
              icon={CircleDollarSign}
              label="Quotes created"
              value={summary.totals.quotes}
              helper="Quotation engine output"
              tone="violet"
            />
          </section>

          <section className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              icon={ShieldAlert}
              label="Needs approval"
              value={summary.totals.needs_approval}
              helper={`${summary.totals.pending_drafts} pending drafts`}
              tone={summary.totals.needs_approval ? "red" : "slate"}
            />
            <MetricCard
              icon={CalendarClock}
              label="Due follow-ups"
              value={summary.totals.due_followups}
              helper="Scheduled tasks due now"
              tone={summary.totals.due_followups ? "orange" : "slate"}
            />
            <MetricCard
              icon={TrendingUp}
              label="Lead → quote"
              value={percent(summary.conversion.lead_to_quote_rate)}
              helper={`${summary.conversion.quotes_created} quote(s) from ${summary.conversion.leads_created} lead(s)`}
              tone="green"
            />
            <MetricCard
              icon={CheckCircle2}
              label="Quote acceptance"
              value={percent(summary.conversion.quote_acceptance_rate)}
              helper={`${summary.conversion.quotes_accepted} accepted quote(s)`}
              tone="blue"
            />
          </section>

          <section className="mt-7 grid gap-4 xl:grid-cols-3">
            <Card className="p-5 xl:col-span-1">
              <h2 className="font-bold">Revenue signal</h2>
              <p className="mt-1 text-xs leading-5 text-[#747973]">
                Quote value is the cleanest early revenue proxy before full accounting lands.
              </p>
              <div className="mt-5 space-y-4">
                <div className="rounded-2xl bg-[#f7f6f2] p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#8a8e88]">
                    Open quote value
                  </p>
                  <p className="mt-2 text-2xl font-bold tracking-[-0.03em]">
                    {money(summary.conversion.open_quote_value)}
                  </p>
                </div>
                <div className="rounded-2xl bg-green-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-green-700">
                    Accepted quote value
                  </p>
                  <p className="mt-2 text-2xl font-bold tracking-[-0.03em] text-green-800">
                    {money(summary.conversion.accepted_quote_value)}
                  </p>
                </div>
              </div>
            </Card>
            <BucketPanel
              title="Channel mix"
              description="Which connected source is producing message volume."
              items={summary.inbox_by_provider}
            />
            <BucketPanel
              title="Approval queue health"
              description="Current status distribution across conversations."
              items={summary.thread_statuses}
            />
          </section>

          <section className="mt-4 grid gap-4 xl:grid-cols-3">
            <BucketPanel
              title="Lead stages"
              description="Pipeline spread across sales stages."
              items={summary.lead_stages}
            />
            <BucketPanel
              title="Lead sources"
              description="Where fresh leads entered BeoOS."
              items={summary.lead_sources}
            />
            <BucketPanel
              title="Lead temperature"
              description="AI qualification signal across open leads."
              items={summary.lead_temperatures}
            />
          </section>

          <section className="mt-4 grid gap-4 xl:grid-cols-3">
            <BucketPanel
              title="Quote status"
              description="Quotation progress and value by state."
              items={summary.quote_statuses}
              showValue
            />
            <BucketPanel
              title="Follow-up status"
              description="Follow-up automation health."
              items={summary.follow_up_statuses}
            />
            <Card className="p-5">
              <h2 className="font-bold">Recent operating activity</h2>
              <p className="mt-1 text-xs leading-5 text-[#747973]">
                Latest inbox, CRM, and quotation movements for this business.
              </p>
              <div className="mt-5 space-y-3">
                {summary.recent_activity.length === 0 ? (
                  <p className="rounded-xl bg-[#f7f6f2] p-4 text-sm text-[#747973]">
                    No recent activity yet.
                  </p>
                ) : (
                  summary.recent_activity.map((item) => (
                    <Link
                      key={`${item.label}-${item.occurred_at}-${item.detail}`}
                      href={item.href ?? "/dashboard/analytics"}
                      className="group block rounded-xl border p-3 transition hover:border-[#ed633f]/50 hover:bg-orange-50/30"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#90948f]">
                            {item.label}
                          </p>
                          <p className="mt-1 line-clamp-2 text-sm font-bold">{item.detail}</p>
                          <p className="mt-1 text-xs text-[#747973]">
                            {dateTime(item.occurred_at)}
                          </p>
                        </div>
                        <ArrowUpRight className="size-4 shrink-0 text-[#ed633f] opacity-0 transition group-hover:opacity-100" />
                      </div>
                    </Link>
                  ))
                )}
              </div>
            </Card>
          </section>
        </>
      )}
    </div>
  );
}

export default async function AnalyticsPage() {
  try {
    const business = await activeBusiness();
    if (!business) {
      return (
        <div className="mx-auto max-w-5xl px-4 py-8 sm:px-5 md:px-8">
          <EmptyState />
        </div>
      );
    }
    const summary = await beoApi.analytics(business.id);
    return <AnalyticsContent businessName={business.name} summary={summary} />;
  } catch {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-5 md:px-8">
        <Card className="p-8">
          <div className="flex items-start gap-4">
            <div className="grid size-11 place-items-center rounded-2xl bg-red-50 text-red-700">
              <Activity className="size-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold">Analytics could not load</h1>
              <p className="mt-2 text-sm leading-6 text-[#747973]">
                Confirm the backend deployment includes Module 4.1 and that your user still has
                access to the selected business.
              </p>
            </div>
          </div>
        </Card>
      </div>
    );
  }
}

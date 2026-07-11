import { ArrowUpRight, CalendarClock, CircleDollarSign, Inbox, Trophy, UsersRound } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { activeBusiness, beoApi, type CRMLead, type CRMStats } from "@/lib/api";

export const metadata = { title: "CRM pipeline" };

const stages = [
  ["new", "New"],
  ["contacted", "Contacted"],
  ["qualified", "Qualified"],
  ["quote_needed", "Quote needed"],
  ["quoted", "Quoted"],
  ["deposit_pending", "Deposit pending"],
  ["won", "Won"],
  ["lost", "Lost"],
] as const;

const stageStyles: Record<string, string> = {
  new: "bg-blue-50 text-blue-700",
  contacted: "bg-violet-50 text-violet-700",
  qualified: "bg-emerald-50 text-emerald-700",
  quote_needed: "bg-amber-50 text-amber-700",
  quoted: "bg-orange-50 text-orange-700",
  deposit_pending: "bg-cyan-50 text-cyan-700",
  won: "bg-green-50 text-green-700",
  lost: "bg-zinc-100 text-zinc-600",
};

function money(value: string | null | undefined, currency = "NGN") {
  const amount = Number(value ?? 0);
  if (!amount) return "No value set";
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
}

function groupByStage(leads: CRMLead[]) {
  return stages.map(([stage, label]) => ({
    stage,
    label,
    leads: leads.filter((lead) => lead.stage === stage),
  }));
}

export default async function CRMPage() {
  let leads: CRMLead[] = [];
  let stats: CRMStats | null = null;
  let businessName = "Current business";

  try {
    const business = await activeBusiness();
    if (business) {
      businessName = business.name;
      [leads, stats] = await Promise.all([
        beoApi.crmLeads(business.id),
        beoApi.crmStats(business.id),
      ]);
    }
  } catch {
    leads = [];
    stats = null;
  }

  const grouped = groupByStage(leads);

  return (
    <div className="mx-auto max-w-[1500px] px-4 py-8 sm:px-5 md:px-8">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#90948f]">{businessName}</p>
      <h1 className="mt-1 text-2xl font-bold tracking-[-0.035em] sm:text-3xl">CRM lead pipeline</h1>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-[#747973]">
        Conversations that look like sales opportunities become structured leads here. This is where BeoOS tracks stage, budget, deadline, service, and follow-up.
      </p>

      <section className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Card className="flex items-center gap-4 p-4">
          <div className="grid size-10 place-items-center rounded-xl bg-blue-50 text-blue-700"><Inbox className="size-4" /></div>
          <div><p className="text-2xl font-bold">{stats?.total ?? 0}</p><p className="text-xs text-[#747973]">Total leads</p></div>
        </Card>
        <Card className="flex items-center gap-4 p-4">
          <div className="grid size-10 place-items-center rounded-xl bg-emerald-50 text-emerald-700"><UsersRound className="size-4" /></div>
          <div><p className="text-2xl font-bold">{stats?.open ?? 0}</p><p className="text-xs text-[#747973]">Open pipeline</p></div>
        </Card>
        <Card className="flex items-center gap-4 p-4">
          <div className="grid size-10 place-items-center rounded-xl bg-amber-50 text-amber-700"><CircleDollarSign className="size-4" /></div>
          <div><p className="text-lg font-bold">{money(stats?.estimated_open_value)}</p><p className="text-xs text-[#747973]">Open value</p></div>
        </Card>
        <Card className="flex items-center gap-4 p-4">
          <div className="grid size-10 place-items-center rounded-xl bg-orange-50 text-orange-700"><CalendarClock className="size-4" /></div>
          <div><p className="text-2xl font-bold">{stats?.needs_follow_up ?? 0}</p><p className="text-xs text-[#747973]">Needs follow-up</p></div>
        </Card>
        <Card className="flex items-center gap-4 p-4">
          <div className="grid size-10 place-items-center rounded-xl bg-green-50 text-green-700"><Trophy className="size-4" /></div>
          <div><p className="text-2xl font-bold">{stats?.won ?? 0}</p><p className="text-xs text-[#747973]">Won deals</p></div>
        </Card>
      </section>

      {leads.length === 0 ? (
        <Card className="mt-7 grid min-h-72 place-items-center p-8 text-center">
          <div>
            <UsersRound className="mx-auto size-8 text-[#ed633f]" />
            <h2 className="mt-4 font-bold">No CRM leads yet</h2>
            <p className="mt-2 max-w-md text-sm leading-6 text-[#747973]">
              Open an inbox conversation and click “Create CRM lead”. BeoOS will pull the service, budget, deadline, source, and contact where available.
            </p>
          </div>
        </Card>
      ) : (
        <section className="mt-7 grid gap-4 xl:grid-cols-4">
          {grouped.map(({ stage, label, leads: stageLeads }) => (
            <Card key={stage} className="overflow-hidden">
              <div className="flex items-center justify-between border-b bg-[#fbfaf7] px-4 py-3">
                <div>
                  <h2 className="text-sm font-bold">{label}</h2>
                  <p className="text-xs text-[#8a8e88]">{stageLeads.length} lead{stageLeads.length === 1 ? "" : "s"}</p>
                </div>
                <Badge className={stageStyles[stage]}>{stage.replaceAll("_", " ")}</Badge>
              </div>
              <div className="space-y-3 p-3">
                {stageLeads.length === 0 ? (
                  <p className="rounded-xl bg-[#f7f6f2] p-4 text-xs text-[#747973]">No leads in this stage.</p>
                ) : (
                  stageLeads.map((lead) => (
                    <Link
                      key={lead.id}
                      href={lead.thread_id ? `/dashboard/inbox/${lead.thread_id}` : "/dashboard/crm"}
                      className="group block rounded-xl border bg-white p-4 transition hover:border-[#ed633f]/40 hover:bg-[#fffaf7]"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <h3 className="line-clamp-2 text-sm font-bold text-[#20242b]">{lead.title}</h3>
                        <ArrowUpRight className="mt-0.5 size-4 shrink-0 text-[#9a9f98] opacity-0 transition group-hover:opacity-100" />
                      </div>
                      <p className="mt-2 truncate text-xs text-[#747973]">
                        {lead.contact_name || lead.contact_email || lead.contact_phone || "Unknown contact"}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Badge className="bg-slate-100 text-slate-700">{lead.source.replaceAll("_", " ")}</Badge>
                        {lead.service && <Badge className="bg-violet-50 text-violet-700">{lead.service}</Badge>}
                      </div>
                      <dl className="mt-3 space-y-1 text-xs text-[#747973]">
                        <div className="flex justify-between gap-3"><dt>Budget</dt><dd className="font-semibold text-[#30343a]">{lead.budget || money(lead.estimated_value, lead.currency)}</dd></div>
                        <div className="flex justify-between gap-3"><dt>Deadline</dt><dd className="truncate font-semibold text-[#30343a]">{lead.deadline || "Not set"}</dd></div>
                        <div className="flex justify-between gap-3"><dt>Probability</dt><dd className="font-semibold text-[#30343a]">{lead.probability}%</dd></div>
                      </dl>
                    </Link>
                  ))
                )}
              </div>
            </Card>
          ))}
        </section>
      )}
    </div>
  );
}

import { Activity, Filter, ShieldCheck, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { activeBusiness, beoApi, type WorkflowTraceSummary } from "@/lib/api";

export const metadata = { title: "Workflow traces" };

export default async function TracesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  let traces: WorkflowTraceSummary[] = [];
  let businessId: string | null = null;
  try {
    const business = await activeBusiness();
    if (business) {
      businessId = business.id;
      const filters: Record<string, string> = {};
      for (const key of [
        "workflow",
        "status",
        "channel",
        "customer",
        "date_from",
        "date_to",
        "approval_state",
        "outcome",
        "model",
        "failure_type",
      ]) {
        const value = params[key];
        if (typeof value === "string" && value) filters[key] = value;
      }
      traces = await beoApi.traces(business.id, filters);
    }
  } catch {}

  return (
    <div className="mx-auto max-w-6xl px-5 py-8 md:px-8">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#90948f]">
        Operations
      </p>
      <h1 className="mt-1 text-3xl font-bold tracking-[-0.035em]">Workflow traces</h1>
      <p className="mt-2 text-sm text-[#747973]">
        Inspect operational evidence and decisions without exposing hidden model reasoning.
      </p>

      <Card className="mt-6 p-4">
        <form className="grid gap-3 md:grid-cols-4">
          <FilterInput name="workflow" label="Workflow key" value={params.workflow} />
          <FilterInput name="status" label="Status" value={params.status} />
          <FilterInput name="channel" label="Channel" value={params.channel} />
          <FilterInput name="customer" label="Customer ID" value={params.customer} />
          <FilterInput name="date_from" label="From (ISO date)" value={params.date_from} />
          <FilterInput name="date_to" label="To (ISO date)" value={params.date_to} />
          <FilterInput name="approval_state" label="Approval state" value={params.approval_state} />
          <FilterInput name="outcome" label="Outcome" value={params.outcome} />
          <FilterInput name="model" label="Model" value={params.model} />
          <FilterInput name="failure_type" label="Failure type" value={params.failure_type} />
          <button className="flex h-10 items-center justify-center gap-2 self-end rounded-xl bg-[#ed633f] px-4 text-sm font-semibold text-white">
            <Filter className="size-4" /> Apply filters
          </button>
          <Link
            href="/dashboard/traces"
            className="flex h-10 items-center justify-center self-end rounded-xl border px-4 text-sm font-semibold"
          >
            Clear
          </Link>
        </form>
      </Card>

      <div className="mt-6 space-y-3">
        {traces.map((trace) => (
          <Link key={trace.run_id} href={`/dashboard/traces/${trace.run_id}`}>
            <Card className="mb-3 grid gap-4 p-5 transition hover:border-[#ed633f]/50 md:grid-cols-[1fr_auto]">
              <div>
                <p className="flex items-center gap-2 font-bold">
                  <Activity className="size-4 text-[#ed633f]" />
                  {trace.workflow_name} v{trace.workflow_version}
                </p>
                <p className="mt-1 text-xs text-[#777c76]">
                  {trace.customer_name || "Unlinked customer"} · {trace.channel.replaceAll("_", " ")} ·{" "}
                  {new Date(trace.created_at).toLocaleString()}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {trace.outcome_types.map((outcome) => (
                    <Badge key={outcome} className="bg-emerald-50 text-emerald-800">{outcome}</Badge>
                  ))}
                  {trace.model && <Badge className="bg-slate-100 text-slate-700">{trace.model}</Badge>}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {trace.failure_type ? (
                  <TriangleAlert className="size-4 text-red-600" />
                ) : (
                  <ShieldCheck className="size-4 text-emerald-600" />
                )}
                <Badge className="bg-violet-50 text-violet-700">{trace.status}</Badge>
                {trace.approval_state && (
                  <Badge className="bg-amber-50 text-amber-800">{trace.approval_state}</Badge>
                )}
              </div>
            </Card>
          </Link>
        ))}
        {traces.length === 0 && (
          <Card className="grid min-h-56 place-items-center p-8 text-center">
            <div>
              <Activity className="mx-auto size-8 text-[#ed633f]" />
              <p className="mt-3 font-bold">No workflow traces match these filters.</p>
              <p className="mt-1 text-sm text-[#777c76]">
                New external events will appear after they enter a controlled workflow.
              </p>
            </div>
          </Card>
        )}
      </div>
      {!businessId && <p className="mt-4 text-sm text-red-700">No active business is available.</p>}
    </div>
  );
}

function FilterInput({
  name,
  label,
  value,
}: {
  name: string;
  label: string;
  value: string | string[] | undefined;
}) {
  return (
    <label className="text-xs font-semibold uppercase tracking-wide text-[#777c76]">
      {label}
      <input
        name={name}
        defaultValue={typeof value === "string" ? value : ""}
        className="mt-1 h-10 w-full rounded-xl border px-3 text-sm font-normal normal-case"
      />
    </label>
  );
}

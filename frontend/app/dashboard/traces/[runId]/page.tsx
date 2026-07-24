import { ArrowLeft, Clock, Coins, Workflow } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { activeBusiness, beoApi, type WorkflowTraceDetail } from "@/lib/api";

export const metadata = { title: "Workflow trace" };

export default async function TraceDetailPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;
  let trace: WorkflowTraceDetail | null = null;
  try {
    const business = await activeBusiness();
    if (business) trace = await beoApi.trace(business.id, runId);
  } catch {}

  if (!trace) {
    return (
      <div className="mx-auto max-w-5xl px-5 py-8 md:px-8">
        <Card className="p-8 text-center">Workflow trace could not be loaded.</Card>
      </div>
    );
  }
  const workflow = trace.workflow;
  return (
    <div className="mx-auto max-w-6xl px-5 py-8 md:px-8">
      <Link href="/dashboard/traces" className="inline-flex items-center gap-2 text-sm font-semibold">
        <ArrowLeft className="size-4" /> All traces
      </Link>
      <div className="mt-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#90948f]">
            Operational trace
          </p>
          <h1 className="mt-1 text-3xl font-bold tracking-[-0.035em]">
            {String(workflow.name || workflow.key)}
          </h1>
          <p className="mt-2 font-mono text-xs text-[#777c76]">{trace.run_id}</p>
        </div>
        <div className="flex gap-2">
          <Badge className="bg-violet-50 text-violet-700">{String(workflow.status)}</Badge>
          <Badge className="bg-slate-100 text-slate-700">
            v{String(workflow.version)} · {String(workflow.deployment_mode)}
          </Badge>
        </div>
      </div>

      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric icon={Workflow} label="Steps" value={String(trace.steps.length)} />
        <Metric icon={Clock} label="AI latency" value={`${trace.latency_ms} ms`} />
        <Metric icon={Coins} label="Estimated cost" value={trace.estimated_cost} />
        <Metric icon={Workflow} label="Retries" value={String(trace.retry_history.reduce((sum, item) => sum + Number(item.attempt_count || 0), 0))} />
      </div>

      <div className="mt-6 space-y-4">
        <TraceSection number={1} title="Trigger" value={trace.trigger} />
        <TraceSection number={2} title="Customer and channel" value={trace.customer_and_channel} />
        <TraceSection number={3} title="Workflow version" value={trace.workflow} />
        <TraceSection number={4} title="Business context sources" value={trace.business_context_sources} />
        <TraceSection number={5} title="Extracted information" value={trace.extracted_information} />
        <TraceSection number={6} title="Missing information" value={trace.missing_information} />
        <TraceSection number={7} title="AI operational summary" value={trace.ai_operational_summary} />
        <TraceSection number={8} title="Policy checks" value={trace.policy_checks} />
        <TraceSection number={9} title="Deterministic calculations" value={trace.deterministic_calculations} />
        <TraceSection number={10} title="Tool calls" value={trace.tool_calls} />
        <TraceSection number={11} title="Approval decision" value={trace.approval_decisions} />
        <TraceSection number={12} title="Human edits" value={trace.human_edits} />
        <TraceSection number={13} title="External action" value={trace.external_actions} />
        <TraceSection number={14} title="Result" value={trace.result} />
        <TraceSection number={15} title="Outcome" value={trace.outcomes} />
        <TraceSection number={16} title="Cost" value={{ estimated_cost: trace.estimated_cost }} />
        <TraceSection number={17} title="Latency" value={{ latency_ms: trace.latency_ms }} />
        <TraceSection number={18} title="Retry history" value={trace.retry_history} />
        <TraceSection number={19} title="Error and recovery" value={trace.errors_and_recovery} />
      </div>
    </div>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Workflow;
  label: string;
  value: string;
}) {
  return (
    <Card className="p-4">
      <Icon className="size-4 text-[#ed633f]" />
      <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-[#888d87]">{label}</p>
      <p className="mt-1 font-bold">{value}</p>
    </Card>
  );
}

function TraceSection({ number, title, value }: { number: number; title: string; value: unknown }) {
  const empty =
    value === null ||
    value === "" ||
    (Array.isArray(value) && value.length === 0) ||
    (typeof value === "object" && !Array.isArray(value) && Object.keys(value as object).length === 0);
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-3 border-b bg-[#fbfaf7] px-5 py-3">
        <span className="grid size-7 place-items-center rounded-full bg-[#ed633f]/10 text-xs font-bold text-[#c94f31]">{number}</span>
        <h2 className="font-bold">{title}</h2>
      </div>
      <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap p-5 text-xs leading-5">
        {empty ? "No record" : typeof value === "string" ? value : JSON.stringify(value, null, 2)}
      </pre>
    </Card>
  );
}

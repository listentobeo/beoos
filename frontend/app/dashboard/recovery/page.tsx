import { AlertTriangle, RotateCcw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { RecoveryActions } from "@/components/dashboard/recovery-actions";
import { activeBusiness, beoApi } from "@/lib/api";

export const metadata = { title: "Recovery" };

function Items({
  title,
  rows,
  businessId,
  kind,
}: {
  title: string;
  rows: Array<Record<string, unknown>>;
  businessId: string;
  kind: "job" | "tool" | "reconciliation";
}) {
  return (
    <Card className="p-5">
      <h2 className="font-bold">{title}</h2>
      <div className="mt-4 space-y-3">
        {rows.length ? (
          rows.map((row, index) => (
            <div key={String(row.id ?? index)} className="rounded-2xl border p-4">
              <div className="flex flex-wrap gap-2">
                <Badge className="bg-amber-50 text-amber-800">
                  {String(row.status ?? "needs review")}
                </Badge>
                {row.failure_category ? (
                  <Badge className="bg-red-50 text-red-800">
                    {String(row.failure_category).replaceAll("_", " ")}
                  </Badge>
                ) : null}
              </div>
              <p className="mt-3 text-sm font-semibold">
                {String(row.type ?? row.action_type ?? row.id)}
              </p>
              <RecoveryActions businessId={businessId} row={row} kind={kind} />
              <p className="mt-1 text-xs leading-5 text-[#747973]">
                {String(row.user_message ?? row.last_error ?? row.error ?? "")}
              </p>
            </div>
          ))
        ) : (
          <p className="rounded-xl bg-[#f7f6f2] p-4 text-sm text-[#747973]">
            Nothing currently requires recovery.
          </p>
        )}
      </div>
    </Card>
  );
}

export default async function RecoveryPage() {
  const business = await activeBusiness();
  if (!business) return <div className="p-8">Create a business workspace first.</div>;
  const queue = await beoApi.recoveryQueue(business.id);
  const total =
    queue.durable_jobs.length + queue.tool_calls.length + queue.reconciliations.length;
  return (
    <div className="mx-auto max-w-[1500px] px-4 py-8 sm:px-5 md:px-8">
      <div className="flex items-start gap-3">
        <div className="grid size-11 place-items-center rounded-2xl bg-amber-50 text-amber-800">
          <RotateCcw className="size-5" />
        </div>
        <div>
          <h1 className="text-3xl font-bold">Recovery</h1>
          <p className="mt-1 text-sm text-[#747973]">
            Review retries, dead letters, and unknown external action states.
          </p>
        </div>
      </div>
      {total > 0 && (
        <Card className="mt-5 flex items-center gap-3 border-amber-200 bg-amber-50 p-4">
          <AlertTriangle className="size-5 text-amber-800" />
          <p className="text-sm text-amber-900">
            Unknown external states must be reconciled before retrying.
          </p>
        </Card>
      )}
      <div className="mt-6 grid gap-5 xl:grid-cols-3">
        <Items title="Durable jobs" rows={queue.durable_jobs} businessId={business.id} kind="job" />
        <Items title="Tool calls" rows={queue.tool_calls} businessId={business.id} kind="tool" />
        <Items title="Reconciliations" rows={queue.reconciliations} businessId={business.id} kind="reconciliation" />
      </div>
    </div>
  );
}

import { FilePenLine, ShieldAlert } from "lucide-react";
import { EditableDraft } from "@/components/dashboard/editable-draft";
import { StructuredApprovalCard } from "@/components/dashboard/structured-approval-card";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  activeBusiness,
  beoApi,
  type DraftQueueItem,
  type StructuredApproval,
} from "@/lib/api";

export const metadata = { title: "Needs approval" };

export default async function ApprovalsPage() {
  let businessId: string | null = null;
  let drafts: DraftQueueItem[] = [];
  let approvals: StructuredApproval[] = [];
  try {
    const business = await activeBusiness();
    if (business) {
      businessId = business.id;
      [drafts, approvals] = await Promise.all([
        beoApi.drafts(business.id),
        beoApi.approvals(business.id),
      ]);
    }
  } catch {}

  return (
    <div className="mx-auto max-w-5xl px-5 py-8 md:px-8">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#90948f]">
        Controlled operations
      </p>
      <h1 className="mt-1 text-3xl font-bold tracking-[-0.035em]">Approval queue</h1>
      <p className="mt-2 text-sm text-[#747973]">
        Review the evidence, policy checks, proposed tool, and risk before any controlled action.
      </p>

      <div className="mt-7 space-y-4">
        {approvals.map((approval) => (
          <Card key={approval.id} className="overflow-hidden">
            <div className="flex flex-col gap-3 border-b bg-[#fbfaf7] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="flex items-center gap-2 font-bold">
                  <ShieldAlert className="size-4 text-[#ed633f]" />
                  {approval.proposed_action.type.replaceAll("_", " ")}
                </p>
                <p className="mt-1 text-xs text-[#7d827d]">
                  {approval.workflow.name} · {approval.customer?.name || approval.customer?.email || "No customer"}
                </p>
              </div>
              <Badge className="bg-amber-50 text-amber-800">
                {approval.risk} risk
              </Badge>
            </div>
            {businessId && (
              <StructuredApprovalCard businessId={businessId} approval={approval} />
            )}
          </Card>
        ))}
        {drafts.length > 0 && (
          <div className="pt-4">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#90948f]">
              Legacy draft approvals
            </p>
          </div>
        )}
        {drafts.map((draft) => (
          <Card key={draft.id} className="overflow-hidden">
            <div className="flex flex-col gap-4 border-b bg-[#fbfaf7] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <FilePenLine className="size-4 text-[#ed633f]" />
                  <h2 className="font-bold">{draft.thread_subject}</h2>
                </div>
                <p className="mt-1 text-xs text-[#7d827d]">{draft.contact_name || draft.contact_email}</p>
              </div>
              <Badge className="bg-violet-50 text-violet-700">{draft.category.replaceAll("_", " ")}</Badge>
            </div>
            <div className="p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-[#949893]">Proposed reply</p>
              {draft.policy_reasons.length > 0 && (
                <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-3">
                  <p className="flex items-center gap-2 text-xs font-bold text-amber-900"><ShieldAlert className="size-4" /> Why approval is required</p>
                  <ul className="mt-2 space-y-1 text-xs text-amber-900/75">
                    {draft.policy_reasons.map((reason) => <li key={reason}>• {reason}</li>)}
                  </ul>
                </div>
              )}
              {businessId && <EditableDraft businessId={businessId} draft={draft} />}
            </div>
          </Card>
        ))}
        {drafts.length === 0 && approvals.length === 0 && (
          <Card className="grid min-h-64 place-items-center p-8 text-center">
            <div><FilePenLine className="mx-auto size-8 text-[#ed633f]" /><p className="mt-3 font-bold">No actions need approval.</p><p className="mt-1 text-sm text-[#777c76]">Controlled workflow actions will appear here with their evidence and policy checks.</p></div>
          </Card>
        )}
      </div>
    </div>
  );
}

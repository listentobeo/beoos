import { FilePenLine, ShieldAlert } from "lucide-react";
import { ApproveDraftButton } from "@/components/dashboard/approve-draft-button";
import { DiscardDraftButton } from "@/components/dashboard/discard-draft-button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { activeBusiness, beoApi, type DraftQueueItem } from "@/lib/api";

export const metadata = { title: "Needs approval" };

export default async function ApprovalsPage() {
  let businessId: string | null = null;
  let drafts: DraftQueueItem[] = [];
  try {
    const business = await activeBusiness();
    if (business) {
      businessId = business.id;
      drafts = await beoApi.drafts(business.id);
    }
  } catch {}

  return (
    <div className="mx-auto max-w-5xl px-5 py-8 md:px-8">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#90948f]">AI Email Assistant</p>
      <h1 className="mt-1 text-3xl font-bold tracking-[-0.035em]">Needs approval</h1>
      <p className="mt-2 text-sm text-[#747973]">Sensitive or lower-confidence drafts wait here. Nothing is sent until you approve it.</p>

      <div className="mt-7 space-y-4">
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
              <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-[#373c43]">{draft.body_text}</p>
              {draft.policy_reasons.length > 0 && (
                <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-3">
                  <p className="flex items-center gap-2 text-xs font-bold text-amber-900"><ShieldAlert className="size-4" /> Why approval is required</p>
                  <ul className="mt-2 space-y-1 text-xs text-amber-900/75">
                    {draft.policy_reasons.map((reason) => <li key={reason}>• {reason}</li>)}
                  </ul>
                </div>
              )}
              {businessId && (
                <div className="mt-5 flex flex-wrap justify-end gap-3">
                  <DiscardDraftButton businessId={businessId} draftId={draft.id} />
                  <ApproveDraftButton businessId={businessId} draftId={draft.id} />
                </div>
              )}
            </div>
          </Card>
        ))}
        {drafts.length === 0 && (
          <Card className="grid min-h-64 place-items-center p-8 text-center">
            <div><FilePenLine className="mx-auto size-8 text-[#ed633f]" /><p className="mt-3 font-bold">No drafts need approval.</p><p className="mt-1 text-sm text-[#777c76]">Sensitive replies will appear here automatically.</p></div>
          </Card>
        )}
      </div>
    </div>
  );
}

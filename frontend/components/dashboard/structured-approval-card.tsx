"use client";

import { LoaderCircle, Pencil, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { StructuredApproval } from "@/lib/api";

const reasons = [
  ["wrong_classification", "Wrong classification"],
  ["missing_information", "Missing information"],
  ["wrong_facts", "Wrong facts"],
  ["wrong_tone", "Wrong tone"],
  ["policy_violation", "Policy violation"],
  ["unsafe_promise", "Unsafe promise"],
  ["wrong_price", "Wrong price"],
  ["unnecessary_escalation", "Unnecessary escalation"],
  ["missed_escalation", "Missed escalation"],
  ["customer_context_misunderstood", "Customer context misunderstood"],
  ["other", "Other"],
] as const;

type Decision =
  | "approve"
  | "edit_and_approve"
  | "reject"
  | "request_more_information"
  | "escalate"
  | "cancel";

export function StructuredApprovalCard({
  businessId,
  approval,
}: {
  businessId: string;
  approval: StructuredApproval;
}) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [edited, setEdited] = useState(
    JSON.stringify(approval.proposed_action.payload, null, 2),
  );
  const [reason, setReason] = useState("wrong_facts");
  const [decisionReason, setDecisionReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function decide(action: Decision) {
    setLoading(true);
    setMessage(null);
    try {
      let editedPayload: Record<string, unknown> | undefined;
      if (action === "edit_and_approve") editedPayload = JSON.parse(edited);
      const response = await fetch(
        `/api/beoos/businesses/${businessId}/approvals/${approval.id}/decide`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action,
            edited_payload: editedPayload,
            correction_reason: action === "edit_and_approve" ? reason : undefined,
            decision_reason: decisionReason || `${action.replaceAll("_", " ")} by reviewer`,
          }),
        },
      );
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(`Decision failed (${response.status}): ${detail.slice(0, 180)}`);
      }
      setMessage("Decision recorded. The workflow has been resumed safely.");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Decision failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4 p-5">
      <div className="grid gap-3 text-sm md:grid-cols-2">
        <Info label="Business" value={approval.business_name} />
        <Info
          label="Customer"
          value={approval.customer?.name || approval.customer?.email || "Not linked"}
        />
        <Info
          label="Workflow"
          value={`${approval.workflow.name} v${approval.workflow.version}`}
        />
        <Info label="Proposed action" value={approval.proposed_action.type} />
        <Info label="Confidence" value={approval.confidence ?? "Not reported"} />
        <Info label="Risk" value={approval.risk} />
        <Info
          label="Financial impact"
          value={approval.financial_impact ?? "No amount recorded"}
        />
        <Info
          label="Expires"
          value={approval.expires_at ? new Date(approval.expires_at).toLocaleString() : "No expiry"}
        />
        <Info label="Tool" value={approval.tool?.name ?? "No executable tool"} />
        <Info label="Required role" value={approval.required_role} />
      </div>

      <section className="rounded-xl border bg-[#fbfaf7] p-4">
        <p className="text-xs font-bold uppercase tracking-wide text-[#777c76]">AI summary</p>
        <p className="mt-2 text-sm leading-6">{approval.ai_summary || "No summary supplied."}</p>
      </section>

      <div className="grid gap-3 md:grid-cols-2">
        <JsonPanel label="Policy checks" value={approval.policy_checks} />
        <JsonPanel label="Context sources" value={approval.context_sources} />
      </div>

      {editing ? (
        <div className="space-y-3 rounded-xl border border-orange-200 bg-orange-50/40 p-4">
          <label className="block text-xs font-bold uppercase tracking-wide">
            Edited action payload
            <textarea
              className="mt-2 min-h-64 w-full rounded-xl border bg-white p-3 font-mono text-xs"
              value={edited}
              onChange={(event) => setEdited(event.target.value)}
            />
          </label>
          <label className="block text-xs font-bold uppercase tracking-wide">
            Correction reason
            <select
              className="mt-2 w-full rounded-xl border bg-white px-3 py-2 text-sm normal-case"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            >
              {reasons.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
        </div>
      ) : (
        <JsonPanel label="Proposed payload" value={approval.proposed_action.payload} />
      )}

      <label className="block text-xs font-bold uppercase tracking-wide text-[#777c76]">
        Decision reason
        <textarea
          className="mt-2 min-h-20 w-full rounded-xl border px-3 py-2 text-sm normal-case"
          value={decisionReason}
          onChange={(event) => setDecisionReason(event.target.value)}
          placeholder="Record why this decision is appropriate."
        />
      </label>

      <div className="flex flex-wrap gap-2">
        <Button onClick={() => decide("approve")} disabled={loading}>
          <ShieldCheck className="size-4" /> Approve
        </Button>
        <Button
          variant="outline"
          onClick={() => (editing ? decide("edit_and_approve") : setEditing(true))}
          disabled={loading}
        >
          <Pencil className="size-4" /> {editing ? "Save edits & approve" : "Edit & approve"}
        </Button>
        <Button variant="outline" onClick={() => decide("reject")} disabled={loading}>Reject</Button>
        <Button variant="outline" onClick={() => decide("request_more_information")} disabled={loading}>
          Request information
        </Button>
        <Button variant="outline" onClick={() => decide("escalate")} disabled={loading}>Escalate</Button>
        <Button variant="ghost" onClick={() => decide("cancel")} disabled={loading}>Cancel</Button>
        {loading && <LoaderCircle className="size-5 animate-spin self-center text-[#ed633f]" />}
      </div>
      {message && <p className="text-xs text-[#666b66]">{message}</p>}
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-[#8b908a]">{label}</p>
      <p className="mt-1 font-medium">{value}</p>
    </div>
  );
}

function JsonPanel({ label, value }: { label: string; value: unknown }) {
  return (
    <details className="rounded-xl border bg-white p-4">
      <summary className="cursor-pointer text-xs font-bold uppercase tracking-wide text-[#777c76]">
        {label}
      </summary>
      <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap text-xs leading-5">
        {JSON.stringify(value, null, 2)}
      </pre>
    </details>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";

type RecoveryKind = "job" | "tool" | "reconciliation";

export function RecoveryActions({
  businessId,
  row,
  kind,
}: {
  businessId: string;
  row: Record<string, unknown>;
  kind: RecoveryKind;
}) {
  const router = useRouter();
  const [reason, setReason] = useState("");
  const [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const unknown = row.failure_category === "external_action_unknown";
  const retryable = ["rate_limit", "timeout", "provider_unavailable", "payment_pending"]
    .includes(String(row.failure_category));

  async function submit(action: string) {
    setBusy(true);
    setMessage("");
    const base = `/api/beoos/businesses/${businessId}/recovery`;
    const path = kind === "job"
      ? `${base}/jobs/${row.id}/decision`
      : kind === "tool"
        ? `${base}/tool-calls/${row.id}/reconciliation`
        : `${base}/reconciliations/${row.id}/decision`;
    try {
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: kind === "tool" ? undefined : JSON.stringify({
          action, reason: reason.trim(), provider_reference: reference.trim() || undefined,
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(typeof body?.detail === "string"
          ? body.detail
          : `Recovery action failed (${response.status}).`);
      }
      setMessage(kind === "tool" ? "Review opened in Reconciliations." : "Decision recorded.");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Recovery action failed.");
    } finally {
      setBusy(false);
    }
  }

  if (kind === "tool") {
    return (
      <div className="mt-3">
        <Button size="sm" variant="outline" disabled={busy} onClick={() => submit("open")}>
          {busy ? "Opening…" : "Review recovery"}
        </Button>
        {message && <p className="mt-2 text-xs" role="status">{message}</p>}
      </div>
    );
  }

  const disabled = busy || reason.trim().length < 3;
  return (
    <div className="mt-4 space-y-3">
      <label className="block text-xs font-semibold">
        Reason for this decision
        <textarea
          className="mt-1 w-full rounded-xl border bg-white p-2 text-sm"
          value={reason} onChange={(event) => setReason(event.target.value)}
          maxLength={2000} rows={2} disabled={busy}
        />
      </label>
      {kind === "reconciliation" && (
        <label className="block text-xs font-semibold">
          Provider confirmation reference
          <input
            className="mt-1 w-full rounded-xl border bg-white p-2 text-sm"
            value={reference} onChange={(event) => setReference(event.target.value)}
            maxLength={255} disabled={busy}
          />
        </label>
      )}
      {unknown && <p className="text-xs text-amber-800">Check the provider before resolving this action.</p>}
      <div className="flex flex-wrap gap-2">
        {((kind === "job" && row.can_retry === true)
          || (kind === "reconciliation" && !unknown && retryable && Boolean(row.durable_job_id))) && (
          <Button size="sm" disabled={disabled} onClick={() => submit("retry")}>Retry</Button>
        )}
        {kind === "reconciliation" && (
          <>
            <Button size="sm" variant="outline" disabled={disabled} onClick={() => submit("mark_reconciled")}>
              Confirm completed
            </Button>
            <Button size="sm" variant="outline" disabled={disabled} onClick={() => submit("mark_failed")}>
              Mark failed
            </Button>
          </>
        )}
        <Button size="sm" variant="outline" disabled={disabled} onClick={() => submit("cancel")}>Cancel action</Button>
      </div>
      {message && <p className="text-xs" role="status">{message}</p>}
    </div>
  );
}

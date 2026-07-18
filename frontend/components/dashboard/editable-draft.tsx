"use client";

import { LoaderCircle, Pencil, Save } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApproveDraftButton } from "@/components/dashboard/approve-draft-button";
import { DiscardDraftButton } from "@/components/dashboard/discard-draft-button";
import { Button } from "@/components/ui/button";
import type { DraftView } from "@/lib/api";

const API_URL = "/api/beoos";

export function EditableDraft({
  businessId,
  draft,
}: {
  businessId: string;
  draft: DraftView;
}) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [subject, setSubject] = useState(draft.subject);
  const [bodyText, setBodyText] = useState(draft.body_text);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function save() {
    setLoading(true);
    setMessage(null);
    try {
      const response = await fetch(`${API_URL}/businesses/${businessId}/email/drafts/${draft.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject, body_text: bodyText }),
      });
      if (!response.ok) throw new Error(`Draft could not be saved (${response.status}).`);
      setEditing(false);
      setMessage("Draft saved.");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Draft could not be saved.");
    } finally {
      setLoading(false);
    }
  }

  if (editing) {
    return (
      <div className="mt-4 space-y-3">
        <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-[#90948f]">
          Subject
          <input
            className="mt-1 w-full rounded-xl border px-3 py-2 text-sm font-normal normal-case tracking-normal"
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
          />
        </label>
        <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-[#90948f]">
          Reply body
          <textarea
            className="mt-1 min-h-56 w-full rounded-xl border px-3 py-2 text-sm font-normal leading-6 normal-case tracking-normal"
            value={bodyText}
            onChange={(event) => setBodyText(event.target.value)}
          />
        </label>
        <div className="flex flex-wrap justify-end gap-3">
          <Button type="button" variant="outline" onClick={() => setEditing(false)} disabled={loading}>
            Cancel
          </Button>
          <Button type="button" onClick={save} disabled={loading}>
            {loading ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}
            Save draft
          </Button>
        </div>
        {message && <p className="text-xs text-[#747973]">{message}</p>}
      </div>
    );
  }

  return (
    <>
      <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-[#373c43]">{bodyText}</p>
      {draft.status === "pending" && (
        <div className="mt-4 flex flex-wrap justify-end gap-3">
          <Button type="button" variant="outline" onClick={() => setEditing(true)}>
            <Pencil className="size-4" />
            Edit reply
          </Button>
          <DiscardDraftButton businessId={businessId} draftId={draft.id} />
          <ApproveDraftButton businessId={businessId} draftId={draft.id} />
        </div>
      )}
      {message && <p className="mt-2 text-xs text-[#747973]">{message}</p>}
    </>
  );
}

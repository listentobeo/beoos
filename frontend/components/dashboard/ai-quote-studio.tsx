"use client";

import { Bot, LoaderCircle, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { CRMLead, QuoteAIDraft, QuoteTemplate } from "@/lib/api";

const API_URL = "/api/beoos";

const inputClass =
  "w-full rounded-2xl border bg-white px-4 py-3 text-sm outline-none transition focus:ring-2 focus:ring-[#ed633f]/20";

export function AIQuoteStudio({
  businessId,
  templates,
  leads,
}: {
  businessId: string;
  templates: QuoteTemplate[];
  leads: CRMLead[];
}) {
  const router = useRouter();
  const [prompt, setPrompt] = useState(
    "Create a clear client-ready quote using our price catalogue and template. Include scope, timeline, assumptions, and payment terms.",
  );
  const [visualNotes, setVisualNotes] = useState("");
  const [assetText, setAssetText] = useState("");
  const [leadId, setLeadId] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState<QuoteAIDraft | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedTemplate = useMemo(
    () => templates.find((template) => template.id === templateId),
    [templateId, templates],
  );
  const selectedLead = useMemo(() => leads.find((lead) => lead.id === leadId), [leadId, leads]);

  async function generate() {
    setBusy(true);
    setError(null);
    setDraft(null);
    try {
      const response = await fetch(`${API_URL}/businesses/${businessId}/quotes/ai/draft`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          lead_id: leadId || null,
          template_id: templateId || null,
          template_type: selectedTemplate?.template_type ?? "custom",
          service: selectedLead?.service ?? "",
          budget: selectedLead?.budget ?? "",
          deadline: selectedLead?.deadline ?? "",
          notes: visualNotes,
          reference_assets: assetText
            .split(/\r?\n/)
            .map((item) => item.trim())
            .filter(Boolean)
            .slice(0, 12),
        }),
      });
      const data = (await response.json().catch(() => ({}))) as QuoteAIDraft & { detail?: string };
      if (!response.ok) throw new Error(data.detail ?? `AI quote draft failed (${response.status})`);
      setDraft(data);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not generate quote draft.");
    } finally {
      setBusy(false);
    }
  }

  async function createQuote() {
    if (!draft) return;
    setCreating(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/businesses/${businessId}/quotes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lead_id: draft.lead_id,
          contact_id: draft.contact_id,
          template_id: draft.template_id,
          title: draft.title,
          template_type: draft.template_type,
          input_data: draft.input_data,
        }),
      });
      const data = (await response.json().catch(() => ({}))) as { id?: string; detail?: string };
      if (!response.ok || !data.id) {
        throw new Error(data.detail ?? `Could not create quote (${response.status})`);
      }
      router.push(`/dashboard/quotes/${data.id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create quote.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="overflow-hidden rounded-[28px] border bg-[#101827] text-white shadow-sm">
      <div className="grid gap-5 p-5 lg:grid-cols-[1fr_360px]">
        <div>
          <div className="flex items-center gap-3">
            <div className="grid size-11 place-items-center rounded-2xl bg-[#ed633f]">
              <Bot className="size-5" />
            </div>
            <div>
              <h2 className="text-lg font-black tracking-[-0.03em]">AI quote studio</h2>
              <p className="text-sm text-white/60">
                Tell BeoOS what to prepare. It uses leads, templates, catalogue, and tenant policy.
              </p>
            </div>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-2">
            <select
              value={leadId}
              onChange={(event) => setLeadId(event.target.value)}
              className={`${inputClass} border-white/10 bg-white/10 text-white`}
            >
              <option value="" className="text-slate-900">
                No CRM lead selected
              </option>
              {leads.map((lead) => (
                <option key={lead.id} value={lead.id} className="text-slate-900">
                  {lead.title} · {lead.temperature} · {lead.service ?? "service not set"}
                </option>
              ))}
            </select>
            <select
              value={templateId}
              onChange={(event) => setTemplateId(event.target.value)}
              className={`${inputClass} border-white/10 bg-white/10 text-white`}
            >
              <option value="" className="text-slate-900">
                Let BeoOS choose structure
              </option>
              {templates.map((template) => (
                <option key={template.id} value={template.id} className="text-slate-900">
                  {template.name} · {template.template_type}
                </option>
              ))}
            </select>
          </div>

          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            className="mt-3 min-h-32 w-full rounded-2xl border border-white/10 bg-white/10 p-4 text-sm leading-6 text-white outline-none placeholder:text-white/35 focus:ring-2 focus:ring-[#ed633f]/35"
            placeholder="Example: Make a premium quote for this church ceiling mural using our standard payment terms and include image/preview notes."
          />

          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <textarea
              value={visualNotes}
              onChange={(event) => setVisualNotes(event.target.value)}
              className="min-h-24 rounded-2xl border border-white/10 bg-white/10 p-4 text-sm leading-6 text-white outline-none placeholder:text-white/35 focus:ring-2 focus:ring-[#ed633f]/35"
              placeholder="Design / presentation notes e.g. premium church proposal, cream background, include assumptions."
            />
            <textarea
              value={assetText}
              onChange={(event) => setAssetText(event.target.value)}
              className="min-h-24 rounded-2xl border border-white/10 bg-white/10 p-4 text-sm leading-6 text-white outline-none placeholder:text-white/35 focus:ring-2 focus:ring-[#ed633f]/35"
              placeholder="Reference image/file links, one per line. Upload support will plug into this path later."
            />
          </div>

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs leading-5 text-white/55">
              AI does not send this to the client. It prepares a draft for your review.
            </p>
            <Button
              type="button"
              onClick={generate}
              disabled={busy || !prompt.trim()}
              className="bg-[#ed633f] text-white hover:bg-[#d95836]"
            >
              {busy ? <LoaderCircle className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              Generate quote draft
            </Button>
          </div>
          {error && <p className="mt-3 rounded-2xl bg-red-500/15 p-3 text-sm text-red-100">{error}</p>}
        </div>

        <div className="rounded-3xl border border-white/10 bg-white p-4 text-[#171b23]">
          {draft ? (
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge className="bg-orange-50 text-[#ed633f]">{draft.provider}</Badge>
                <Badge className="bg-slate-100 text-slate-700">{draft.template_type}</Badge>
              </div>
              <h3 className="mt-3 text-xl font-black tracking-[-0.03em]">{draft.title}</h3>
              <p className="mt-2 text-sm leading-6 text-[#667085]">{draft.summary}</p>

              {draft.line_items.length > 0 && (
                <div className="mt-4 rounded-2xl bg-[#fbfaf7] p-3">
                  <p className="text-xs font-black uppercase tracking-[0.16em] text-[#90948f]">
                    Suggested items
                  </p>
                  <div className="mt-2 space-y-2">
                    {draft.line_items.slice(0, 5).map((item, index) => (
                      <div key={`${item.label}-${index}`} className="flex justify-between gap-3 text-sm">
                        <span>{item.label}</span>
                        <span className="font-bold">₦{Number(item.unit_price || 0).toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {draft.missing_information.length > 0 && (
                <div className="mt-4 rounded-2xl bg-amber-50 p-3 text-sm text-amber-800">
                  <p className="font-bold">Missing before sending:</p>
                  <ul className="mt-1 list-disc space-y-1 pl-5">
                    {draft.missing_information.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {draft.warnings.length > 0 && (
                <p className="mt-4 rounded-2xl bg-slate-100 p-3 text-xs leading-5 text-slate-600">
                  {draft.warnings[0]}
                </p>
              )}

              <Button
                type="button"
                onClick={createQuote}
                disabled={creating}
                className="mt-4 w-full bg-[#101827] text-white hover:bg-[#ed633f]"
              >
                {creating ? <LoaderCircle className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
                Create quote from draft
              </Button>
            </div>
          ) : (
            <div className="grid min-h-72 place-items-center text-center">
              <div>
                <Sparkles className="mx-auto size-9 text-[#ed633f]" />
                <h3 className="mt-3 font-black">No draft yet</h3>
                <p className="mt-2 text-sm leading-6 text-[#667085]">
                  Select a lead/template if needed, describe the quote, and BeoOS will prepare the
                  structure before you create it.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

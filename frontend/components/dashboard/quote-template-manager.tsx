"use client";

import { useState } from "react";
import { LoaderCircle, Save, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import type { QuoteTemplate } from "@/lib/api";

const API_URL = "/api/beoos";
const inputClass =
  "w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[#ed633f]/25";

type TemplateDraft = {
  name: string;
  description: string;
  template_type: "custom" | "mural";
  accent_color: string;
  deposit_percent: string;
  summary: string;
  scope: string;
  payment_terms: string;
  timeline: string;
  layout: string;
  assumptions: string;
  exclusions: string;
  warranty: string;
};

function stringField(source: Record<string, unknown>, key: string, fallback = "") {
  const value = source[key];
  return typeof value === "string" ? value : fallback;
}

function draftFromTemplate(template?: QuoteTemplate): TemplateDraft {
  const defaultInput = template?.default_input ?? {};
  const design = template?.design_settings ?? {};
  const terms = template?.terms_settings ?? {};
  return {
    name: template?.name ?? "",
    description: template?.description ?? "",
    template_type: template?.template_type === "mural" ? "mural" : "custom",
    accent_color: stringField(design, "accent_color", "#ed633f"),
    deposit_percent: stringField(defaultInput, "deposit_percent", "50"),
    summary: stringField(defaultInput, "summary"),
    scope: stringField(defaultInput, "scope"),
    payment_terms: stringField(terms, "payment_terms"),
    timeline: stringField(terms, "timeline"),
    layout: stringField(design, "layout", "classic"),
    assumptions: stringField(terms, "assumptions"),
    exclusions: stringField(terms, "exclusions"),
    warranty: stringField(terms, "warranty"),
  };
}

function payloadFromDraft(draft: TemplateDraft, active = true) {
  return {
    name: draft.name.trim(),
    description: draft.description.trim(),
    template_type: draft.template_type,
    field_schema: {},
    default_input: {
      summary: draft.summary.trim(),
      scope: draft.scope.trim(),
      deposit_percent: draft.deposit_percent.trim() || "50",
    },
    design_settings: {
      accent_color: draft.accent_color || "#ed633f",
      layout: draft.layout.trim() || "classic",
    },
    terms_settings: {
      payment_terms: draft.payment_terms.trim(),
      timeline: draft.timeline.trim(),
      assumptions: draft.assumptions.trim(),
      exclusions: draft.exclusions.trim(),
      warranty: draft.warranty.trim(),
    },
    active,
  };
}

export function QuoteTemplateManager({
  businessId,
  templates,
}: {
  businessId: string;
  templates: QuoteTemplate[];
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function request(path: string, init: RequestInit) {
    const response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init.headers,
      },
    });
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      throw new Error(payload?.detail || `Request failed (${response.status})`);
    }
    return response;
  }

  async function create(draft: TemplateDraft) {
    setBusy("new");
    setMessage(null);
    try {
      await request(`/businesses/${businessId}/quotes/templates`, {
        method: "POST",
        body: JSON.stringify(payloadFromDraft(draft)),
      });
      setMessage("Quote template created.");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Template could not be created.");
    } finally {
      setBusy(null);
    }
  }

  async function update(template: QuoteTemplate, draft: TemplateDraft) {
    setBusy(template.id);
    setMessage(null);
    try {
      await request(`/businesses/${businessId}/quotes/templates/${template.id}`, {
        method: "PATCH",
        body: JSON.stringify(payloadFromDraft(draft, template.active)),
      });
      setMessage("Quote template updated.");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Template could not be updated.");
    } finally {
      setBusy(null);
    }
  }

  async function deactivate(template: QuoteTemplate) {
    if (!confirm(`Deactivate "${template.name}"? Existing quotes will remain.`)) return;
    setBusy(template.id);
    setMessage(null);
    try {
      await fetch(`${API_URL}/businesses/${businessId}/quotes/templates/${template.id}`, {
        method: "DELETE",
      });
      setMessage("Quote template deactivated.");
      router.refresh();
    } catch {
      setMessage("Template could not be deactivated.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-5">
      <TemplateEditor
        title="Create quote template"
        description="Save reusable quote defaults for bulk purchases, services, packages, murals, or any tenant-specific offer."
        busy={busy === "new"}
        onSave={create}
      />

      {message && <p className="text-sm text-[#747973]">{message}</p>}

      <div className="grid gap-4 xl:grid-cols-2">
        {templates.map((template) => (
          <TemplateEditor
            key={template.id}
            template={template}
            title={template.name}
            description={`${template.template_type} template · updated ${new Date(template.updated_at).toLocaleDateString()}`}
            busy={busy === template.id}
            onSave={(draft) => update(template, draft)}
            onDeactivate={() => deactivate(template)}
          />
        ))}
      </div>
    </div>
  );
}

function TemplateEditor({
  template,
  title,
  description,
  busy,
  onSave,
  onDeactivate,
}: {
  template?: QuoteTemplate;
  title: string;
  description: string;
  busy: boolean;
  onSave: (draft: TemplateDraft) => void;
  onDeactivate?: () => void;
}) {
  const [draft, setDraft] = useState<TemplateDraft>(() => draftFromTemplate(template));

  function setField<K extends keyof TemplateDraft>(key: K, value: TemplateDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  return (
    <div className="rounded-2xl border bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="font-bold">{title}</h3>
          <p className="mt-1 text-sm leading-6 text-[#747973]">{description}</p>
        </div>
        <div className="flex gap-2">
          {onDeactivate && (
            <Button type="button" variant="outline" size="sm" onClick={onDeactivate} disabled={busy}>
              <Trash2 className="size-4" />
              Deactivate
            </Button>
          )}
          <Button type="button" size="sm" onClick={() => onSave(draft)} disabled={busy}>
            {busy ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}
            Save
          </Button>
        </div>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1fr_320px]">
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-xs font-bold text-[#5f655f]">
            Template name
            <input className={`${inputClass} mt-1`} value={draft.name} onChange={(event) => setField("name", event.target.value)} placeholder="e.g. Bulk art supplies" required />
          </label>
          <label className="text-xs font-bold text-[#5f655f]">
            Template type
            <select className={`${inputClass} mt-1`} value={draft.template_type} onChange={(event) => setField("template_type", event.target.value as "custom" | "mural")}>
              <option value="custom">Custom / bulk / service</option>
              <option value="mural">Mural calculator</option>
            </select>
          </label>
          <label className="text-xs font-bold text-[#5f655f]">
            Brand/accent color
            <div className="mt-1 flex gap-2">
              <input className="h-10 w-14 rounded-xl border bg-white p-1" type="color" value={draft.accent_color} onChange={(event) => setField("accent_color", event.target.value)} />
              <input className={inputClass} value={draft.accent_color} onChange={(event) => setField("accent_color", event.target.value)} placeholder="#ed633f" />
            </div>
          </label>
          <label className="text-xs font-bold text-[#5f655f]">
            Deposit %
            <input className={`${inputClass} mt-1`} value={draft.deposit_percent} onChange={(event) => setField("deposit_percent", event.target.value)} placeholder="50" type="number" min="0" />
          </label>
          <label className="text-xs font-bold text-[#5f655f] md:col-span-2">
            Internal description
            <textarea className={`${inputClass} mt-1`} value={draft.description} onChange={(event) => setField("description", event.target.value)} placeholder="What this template is for" />
          </label>
          <label className="text-xs font-bold text-[#5f655f] md:col-span-2">
            Client-facing summary
            <textarea className={`${inputClass} mt-1`} value={draft.summary} onChange={(event) => setField("summary", event.target.value)} placeholder="Short opening summary clients will see" />
          </label>
          <label className="text-xs font-bold text-[#5f655f] md:col-span-2">
            Default scope
            <textarea className={`${inputClass} mt-1`} value={draft.scope} onChange={(event) => setField("scope", event.target.value)} placeholder="What is included in this quote" />
          </label>
          <label className="text-xs font-bold text-[#5f655f]">
            Timeline
            <input className={`${inputClass} mt-1`} value={draft.timeline} onChange={(event) => setField("timeline", event.target.value)} placeholder="e.g. 3-5 working days" />
          </label>
          <label className="text-xs font-bold text-[#5f655f]">
            Layout
            <select className={`${inputClass} mt-1`} value={draft.layout} onChange={(event) => setField("layout", event.target.value)}>
              <option value="classic">Classic</option>
              <option value="bold">Bold header</option>
              <option value="minimal">Minimal</option>
            </select>
          </label>
          <label className="text-xs font-bold text-[#5f655f] md:col-span-2">
            Payment terms
            <textarea className={`${inputClass} mt-1`} value={draft.payment_terms} onChange={(event) => setField("payment_terms", event.target.value)} placeholder="e.g. 50% deposit, 50% before delivery" />
          </label>
          <label className="text-xs font-bold text-[#5f655f] md:col-span-2">
            Assumptions
            <textarea className={`${inputClass} mt-1`} value={draft.assumptions} onChange={(event) => setField("assumptions", event.target.value)} placeholder="Things assumed in this quote" />
          </label>
          <label className="text-xs font-bold text-[#5f655f] md:col-span-2">
            Exclusions
            <textarea className={`${inputClass} mt-1`} value={draft.exclusions} onChange={(event) => setField("exclusions", event.target.value)} placeholder="What is not covered" />
          </label>
          <label className="text-xs font-bold text-[#5f655f] md:col-span-2">
            Warranty/support note
            <textarea className={`${inputClass} mt-1`} value={draft.warranty} onChange={(event) => setField("warranty", event.target.value)} placeholder="After-sale support, warranty, or service note" />
          </label>
        </div>

        <TemplatePreview draft={draft} />
      </div>
    </div>
  );
}

function TemplatePreview({ draft }: { draft: TemplateDraft }) {
  return (
    <aside className="overflow-hidden rounded-2xl border bg-[#f7f6f2]">
      <div className="p-5 text-white" style={{ backgroundColor: draft.accent_color || "#ed633f" }}>
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-white/65">Client preview</p>
        <h4 className="mt-2 text-2xl font-black tracking-[-0.04em]">{draft.name || "Template name"}</h4>
        <p className="mt-2 text-sm text-white/75">{draft.description || "Internal description appears here while you design."}</p>
      </div>
      <div className="space-y-4 p-5 text-sm">
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-[#858a84]">Summary</p>
          <p className="mt-1 leading-6 text-[#30343a]">{draft.summary || "Client-facing summary preview."}</p>
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-[#858a84]">Scope</p>
          <p className="mt-1 leading-6 text-[#30343a]">{draft.scope || "Default scope preview."}</p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl bg-white p-3">
            <p className="text-xs text-[#747973]">Deposit</p>
            <p className="font-bold">{draft.deposit_percent || 0}%</p>
          </div>
          <div className="rounded-xl bg-white p-3">
            <p className="text-xs text-[#747973]">Layout</p>
            <p className="font-bold capitalize">{draft.layout || "classic"}</p>
          </div>
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-[#858a84]">Payment terms</p>
          <p className="mt-1 leading-6 text-[#30343a]">{draft.payment_terms || "Payment terms preview."}</p>
        </div>
      </div>
    </aside>
  );
}

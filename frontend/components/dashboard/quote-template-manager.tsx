"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { LoaderCircle, Save, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import type { QuoteTemplate } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const inputClass =
  "w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[#ed633f]/25";

function stringField(source: Record<string, unknown>, key: string, fallback = "") {
  const value = source[key];
  return typeof value === "string" ? value : fallback;
}

function payloadFromForm(formData: FormData, active = true) {
  const templateType = String(formData.get("template_type") ?? "custom");
  const accentColor = String(formData.get("accent_color") ?? "#ed633f").trim() || "#ed633f";
  return {
    name: String(formData.get("name") ?? "").trim(),
    description: String(formData.get("description") ?? "").trim(),
    template_type: templateType === "mural" ? "mural" : "custom",
    field_schema: {},
    default_input: {
      summary: String(formData.get("summary") ?? "").trim(),
      scope: String(formData.get("scope") ?? "").trim(),
      deposit_percent: String(formData.get("deposit_percent") ?? "").trim() || "50",
    },
    design_settings: {
      accent_color: accentColor,
      layout: String(formData.get("layout") ?? "classic").trim() || "classic",
    },
    terms_settings: {
      payment_terms: String(formData.get("payment_terms") ?? "").trim(),
      timeline: String(formData.get("timeline") ?? "").trim(),
      assumptions: String(formData.get("assumptions") ?? "").trim(),
      exclusions: String(formData.get("exclusions") ?? "").trim(),
      warranty: String(formData.get("warranty") ?? "").trim(),
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
  const { getToken } = useAuth();
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function request(path: string, init: RequestInit) {
    const token = await getToken();
    const response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...init.headers,
      },
    });
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      throw new Error(payload?.detail || `Request failed (${response.status})`);
    }
    return response;
  }

  async function create(formData: FormData) {
    setBusy("new");
    setMessage(null);
    try {
      await request(`/businesses/${businessId}/quotes/templates`, {
        method: "POST",
        body: JSON.stringify(payloadFromForm(formData)),
      });
      setMessage("Quote template created.");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Template could not be created.");
    } finally {
      setBusy(null);
    }
  }

  async function update(template: QuoteTemplate, formData: FormData) {
    setBusy(template.id);
    setMessage(null);
    try {
      await request(`/businesses/${businessId}/quotes/templates/${template.id}`, {
        method: "PATCH",
        body: JSON.stringify(payloadFromForm(formData, template.active)),
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
      const token = await getToken();
      await fetch(`${API_URL}/businesses/${businessId}/quotes/templates/${template.id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
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
      <form action={create} className="rounded-2xl border bg-[#fbfaf7] p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="font-bold">Create quote template</h2>
            <p className="mt-1 text-sm leading-6 text-[#747973]">
              Save reusable quote defaults for bulk purchases, services, packages, murals, or any
              tenant-specific offer.
            </p>
          </div>
          <Button type="submit" disabled={busy === "new"}>
            {busy === "new" ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}
            Save template
          </Button>
        </div>
        <TemplateFields />
      </form>

      {message && <p className="text-sm text-[#747973]">{message}</p>}

      <div className="grid gap-4 lg:grid-cols-2">
        {templates.map((template) => (
          <form
            key={template.id}
            action={(formData) => update(template, formData)}
            className="rounded-2xl border bg-white p-5"
          >
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <h3 className="font-bold">{template.name}</h3>
                <p className="mt-1 text-xs text-[#747973]">
                  {template.template_type} template · updated{" "}
                  {new Date(template.updated_at).toLocaleDateString()}
                </p>
              </div>
              <div className="flex gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => deactivate(template)} disabled={busy === template.id}>
                  <Trash2 className="size-4" /> Deactivate
                </Button>
                <Button type="submit" size="sm" disabled={busy === template.id}>
                  {busy === template.id ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}
                  Save
                </Button>
              </div>
            </div>
            <TemplateFields template={template} compact />
          </form>
        ))}
      </div>
    </div>
  );
}

function TemplateFields({ template, compact = false }: { template?: QuoteTemplate; compact?: boolean }) {
  const defaultInput = template?.default_input ?? {};
  const design = template?.design_settings ?? {};
  const terms = template?.terms_settings ?? {};
  return (
    <div className={`mt-4 grid gap-3 ${compact ? "md:grid-cols-2" : "md:grid-cols-4"}`}>
      <input className={inputClass} name="name" defaultValue={template?.name ?? ""} placeholder="Template name e.g. Bulk art supplies" required />
      <select className={inputClass} name="template_type" defaultValue={template?.template_type ?? "custom"}>
        <option value="custom">Custom / bulk / service</option>
        <option value="mural">Mural calculator</option>
      </select>
      <input className={inputClass} name="accent_color" defaultValue={stringField(design, "accent_color", "#ed633f")} placeholder="#ed633f" />
      <input className={inputClass} name="deposit_percent" defaultValue={stringField(defaultInput, "deposit_percent", "50")} placeholder="Deposit %" />
      <textarea className={`${inputClass} md:col-span-2`} name="description" defaultValue={template?.description ?? ""} placeholder="Internal description" />
      <textarea className={`${inputClass} md:col-span-2`} name="summary" defaultValue={stringField(defaultInput, "summary")} placeholder="Client-facing summary" />
      <textarea className={`${inputClass} md:col-span-2`} name="scope" defaultValue={stringField(defaultInput, "scope")} placeholder="Default scope" />
      <textarea className={`${inputClass} md:col-span-2`} name="payment_terms" defaultValue={stringField(terms, "payment_terms")} placeholder="Payment terms" />
      <input className={inputClass} name="timeline" defaultValue={stringField(terms, "timeline")} placeholder="Timeline" />
      <input className={inputClass} name="layout" defaultValue={stringField(design, "layout", "classic")} placeholder="Layout e.g. classic" />
      <textarea className={`${inputClass} md:col-span-2`} name="assumptions" defaultValue={stringField(terms, "assumptions")} placeholder="Assumptions" />
      <textarea className={`${inputClass} md:col-span-2`} name="exclusions" defaultValue={stringField(terms, "exclusions")} placeholder="Exclusions" />
      <textarea className={`${inputClass} md:col-span-2`} name="warranty" defaultValue={stringField(terms, "warranty")} placeholder="Warranty/support note" />
    </div>
  );
}

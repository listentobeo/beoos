"use client";

import { useMemo, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { FileText, LoaderCircle, PackagePlus, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import type { PriceItem, QuoteTemplate } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const inputClass =
  "w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[#ed633f]/25";

type LineItem = {
  label: string;
  quantity: string;
  unit_price: string;
};

export function FlexibleQuoteForm({
  businessId,
  templates,
  prices,
}: {
  businessId: string;
  templates: QuoteTemplate[];
  prices: PriceItem[];
}) {
  const { getToken } = useAuth();
  const router = useRouter();
  const customTemplates = templates.filter((template) => template.template_type === "custom");
  const activePrices = prices.filter((price) => price.active);
  const [templateId, setTemplateId] = useState(customTemplates[0]?.id ?? "");
  const [catalogueItemId, setCatalogueItemId] = useState(activePrices[0]?.id ?? "");
  const [lineItems, setLineItems] = useState<LineItem[]>([
    { label: "", quantity: "1", unit_price: "" },
    { label: "", quantity: "1", unit_price: "" },
    { label: "", quantity: "1", unit_price: "" },
  ]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const selectedTemplate = useMemo(
    () => templates.find((template) => template.id === templateId) ?? null,
    [templateId, templates],
  );

  function setLine(index: number, key: keyof LineItem, value: string) {
    setLineItems((items) =>
      items.map((item, itemIndex) => (itemIndex === index ? { ...item, [key]: value } : item)),
    );
  }

  function addBlankLine() {
    setLineItems((items) => [...items, { label: "", quantity: "1", unit_price: "" }]);
  }

  function addCatalogueItem() {
    const item = activePrices.find((price) => price.id === catalogueItemId);
    if (!item) return;
    setLineItems((items) => [
      ...items,
      {
        label: item.label,
        quantity: "1",
        unit_price: String(item.amount_min ?? item.amount_max ?? ""),
      },
    ]);
  }

  async function createQuote(formData: FormData) {
    setLoading(true);
    setMessage(null);
    const usableItems = lineItems.filter((item) => item.label.trim() && Number(item.unit_price) > 0);
    try {
      const token = await getToken();
      const response = await fetch(`${API_URL}/businesses/${businessId}/quotes`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          template_id: templateId || null,
          title: String(formData.get("title") ?? "").trim(),
          template_type: selectedTemplate?.template_type ?? "custom",
          input_data: {
            client_name: String(formData.get("client_name") ?? "").trim(),
            project_title: String(formData.get("title") ?? "").trim(),
            currency: "NGN",
            discount_percent: String(formData.get("discount_percent") ?? "0"),
            tax_percent: String(formData.get("tax_percent") ?? "0"),
            deposit_percent: String(formData.get("deposit_percent") ?? ""),
            line_items: usableItems,
          },
        }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "Quote could not be created.");
      }
      const quote = (await response.json()) as { id: string };
      router.push(`/dashboard/quotes/${quote.id}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Quote could not be created.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form action={createQuote} className="rounded-2xl border bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-bold">Create flexible quote</h2>
          <p className="mt-1 text-sm leading-6 text-[#747973]">
            Use this for bulk purchases, product packages, retainers, and generic service quotes.
          </p>
        </div>
        <Button type="submit" disabled={loading}>
          {loading ? <LoaderCircle className="size-4 animate-spin" /> : <FileText className="size-4" />}
          Create quote
        </Button>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-4">
        <select className={inputClass} value={templateId} onChange={(event) => setTemplateId(event.target.value)}>
          <option value="">No template</option>
          {customTemplates.map((template) => (
            <option key={template.id} value={template.id}>{template.name}</option>
          ))}
        </select>
        <input className={`${inputClass} md:col-span-2`} name="title" placeholder="Quote title e.g. Bulk canvas and paint order" required />
        <input className={inputClass} name="client_name" placeholder="Client name" />
        <input className={inputClass} name="discount_percent" placeholder="Discount %" defaultValue="0" />
        <input className={inputClass} name="tax_percent" placeholder="Tax/VAT %" defaultValue="0" />
        <input className={inputClass} name="deposit_percent" placeholder="Deposit %" defaultValue={String(selectedTemplate?.default_input.deposit_percent ?? "50")} />
      </div>

      <div className="mt-4 rounded-2xl border bg-[#fbfaf7] p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-end">
          <label className="flex-1 text-xs font-bold text-[#5f655f]">
            Add from price catalogue
            <select
              className={`${inputClass} mt-1`}
              value={catalogueItemId}
              onChange={(event) => setCatalogueItemId(event.target.value)}
            >
              {activePrices.length === 0 ? (
                <option value="">No active catalogue items yet</option>
              ) : (
                activePrices.map((price) => (
                  <option key={price.id} value={price.id}>
                    {price.service} · {price.label} · {price.amount_min ?? price.amount_max ?? "No price"}
                  </option>
                ))
              )}
            </select>
          </label>
          <Button
            type="button"
            variant="outline"
            onClick={addCatalogueItem}
            disabled={!catalogueItemId}
          >
            <PackagePlus className="size-4" />
            Add catalogue item
          </Button>
          <Button type="button" variant="outline" onClick={addBlankLine}>
            <Plus className="size-4" />
            Add blank row
          </Button>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        {lineItems.map((item, index) => (
          <div key={index} className="grid gap-3 md:grid-cols-[1fr_120px_160px]">
            <input className={inputClass} value={item.label} onChange={(event) => setLine(index, "label", event.target.value)} placeholder={`Item ${index + 1} name`} />
            <input className={inputClass} value={item.quantity} onChange={(event) => setLine(index, "quantity", event.target.value)} placeholder="Qty" type="number" min="0" />
            <input className={inputClass} value={item.unit_price} onChange={(event) => setLine(index, "unit_price", event.target.value)} placeholder="Unit price" type="number" min="0" />
          </div>
        ))}
      </div>
      {message && <p className="mt-3 text-xs text-[#b5472f]">{message}</p>}
    </form>
  );
}

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

function numberValue(value: string) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function money(value: number) {
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: "NGN",
    maximumFractionDigits: 0,
  }).format(value);
}

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
  const [title, setTitle] = useState("");
  const [clientName, setClientName] = useState("");
  const [discountPercent, setDiscountPercent] = useState("0");
  const [taxPercent, setTaxPercent] = useState("0");
  const [depositPercent, setDepositPercent] = useState(
    String(customTemplates[0]?.default_input.deposit_percent ?? "50"),
  );
  const [lineItems, setLineItems] = useState<LineItem[]>([
    { label: "", quantity: "1", unit_price: "" },
  ]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const selectedTemplate = useMemo(
    () => templates.find((template) => template.id === templateId) ?? null,
    [templateId, templates],
  );
  const subtotal = lineItems.reduce(
    (sum, item) => sum + numberValue(item.quantity) * numberValue(item.unit_price),
    0,
  );
  const discount = subtotal * (numberValue(discountPercent) / 100);
  const taxable = Math.max(subtotal - discount, 0);
  const tax = taxable * (numberValue(taxPercent) / 100);
  const total = taxable + tax;
  const deposit = total * (numberValue(depositPercent) / 100);

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
    setMessage(null);
    const quoteTitle = String(formData.get("title") ?? "").trim();
    const usableItems = lineItems.filter((item) => item.label.trim() && Number(item.unit_price) > 0);
    if (!quoteTitle) {
      setMessage("Add a quote title first.");
      return;
    }
    if (usableItems.length === 0) {
      setMessage("Add at least one priced item before creating the quote.");
      return;
    }
    setLoading(true);
    try {
      const token = await getToken();
      const response = await fetch(`${API_URL}/businesses/${businessId}/quotes`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          template_id: templateId || null,
          title: quoteTitle,
          template_type: selectedTemplate?.template_type ?? "custom",
          input_data: {
            client_name: String(formData.get("client_name") ?? "").trim(),
            project_title: quoteTitle,
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
            Build a client-ready quote from products, packages, retainers, or generic services.
          </p>
        </div>
        <Button type="submit" disabled={loading}>
          {loading ? <LoaderCircle className="size-4 animate-spin" /> : <FileText className="size-4" />}
          Create quote
        </Button>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_320px]">
        <div>
          <div className="grid gap-3 md:grid-cols-4">
            <label className="text-xs font-bold text-[#5f655f]">
              Quote template
              <select
                className={`${inputClass} mt-1`}
                value={templateId}
                onChange={(event) => {
                  setTemplateId(event.target.value);
                  const nextTemplate = templates.find((template) => template.id === event.target.value);
                  if (nextTemplate?.default_input.deposit_percent) {
                    setDepositPercent(String(nextTemplate.default_input.deposit_percent));
                  }
                }}
              >
                <option value="">No template</option>
                {customTemplates.map((template) => (
                  <option key={template.id} value={template.id}>{template.name}</option>
                ))}
              </select>
            </label>
            <label className="text-xs font-bold text-[#5f655f] md:col-span-2">
              Quote title
              <input className={`${inputClass} mt-1`} name="title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="e.g. Bulk canvas and paint order" required />
            </label>
            <label className="text-xs font-bold text-[#5f655f]">
              Client name
              <input className={`${inputClass} mt-1`} name="client_name" value={clientName} onChange={(event) => setClientName(event.target.value)} placeholder="e.g. Grace Schools" />
            </label>
            <label className="text-xs font-bold text-[#5f655f]">
              Discount %
              <input className={`${inputClass} mt-1`} name="discount_percent" value={discountPercent} onChange={(event) => setDiscountPercent(event.target.value)} placeholder="0" type="number" min="0" />
            </label>
            <label className="text-xs font-bold text-[#5f655f]">
              Tax/VAT %
              <input className={`${inputClass} mt-1`} name="tax_percent" value={taxPercent} onChange={(event) => setTaxPercent(event.target.value)} placeholder="0" type="number" min="0" />
            </label>
            <label className="text-xs font-bold text-[#5f655f]">
              Deposit %
              <input className={`${inputClass} mt-1`} name="deposit_percent" value={depositPercent} onChange={(event) => setDepositPercent(event.target.value)} placeholder="50" type="number" min="0" />
            </label>
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
              <Button type="button" variant="outline" onClick={addCatalogueItem} disabled={!catalogueItemId}>
                <PackagePlus className="size-4" />
                Add item
              </Button>
              <Button type="button" variant="outline" onClick={addBlankLine}>
                <Plus className="size-4" />
                Blank row
              </Button>
            </div>
          </div>

          <div className="mt-4 space-y-3">
            <div className="hidden grid-cols-[1fr_120px_160px] gap-3 px-1 text-[11px] font-bold uppercase tracking-wider text-[#858a84] md:grid">
              <span>Item / service</span>
              <span>Quantity</span>
              <span>Unit price</span>
            </div>
            {lineItems.map((item, index) => (
              <div key={index} className="grid gap-3 md:grid-cols-[1fr_120px_160px]">
                <input className={inputClass} value={item.label} onChange={(event) => setLine(index, "label", event.target.value)} placeholder={`Item ${index + 1} name`} />
                <input className={inputClass} value={item.quantity} onChange={(event) => setLine(index, "quantity", event.target.value)} placeholder="Qty" type="number" min="0" />
                <input className={inputClass} value={item.unit_price} onChange={(event) => setLine(index, "unit_price", event.target.value)} placeholder="Unit price" type="number" min="0" />
              </div>
            ))}
          </div>
        </div>

        <aside className="rounded-2xl border bg-[#101827] p-5 text-white">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-white/45">Live quote total</p>
          <h3 className="mt-3 text-xl font-black tracking-[-0.03em]">{title || "Untitled quote"}</h3>
          <p className="mt-1 text-sm text-white/60">{clientName || "Client not set"}</p>
          <div className="mt-5 space-y-3 text-sm">
            <div className="flex justify-between gap-3"><span className="text-white/60">Subtotal</span><strong>{money(subtotal)}</strong></div>
            <div className="flex justify-between gap-3"><span className="text-white/60">Discount</span><strong>{money(discount)}</strong></div>
            <div className="flex justify-between gap-3"><span className="text-white/60">Tax/VAT</span><strong>{money(tax)}</strong></div>
            <div className="border-t border-white/10 pt-3">
              <div className="flex justify-between gap-3 text-lg"><span>Total</span><strong>{money(total)}</strong></div>
              <p className="mt-2 text-xs text-white/50">Deposit: {money(deposit)} ({depositPercent || 0}%)</p>
            </div>
          </div>
          <p className="mt-5 rounded-xl bg-white/10 p-3 text-xs leading-5 text-white/65">
            If this still says ₦0, add at least one item with a unit price before creating the quote.
          </p>
        </aside>
      </div>
      {message && <p className="mt-3 text-xs text-[#b5472f]">{message}</p>}
    </form>
  );
}

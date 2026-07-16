"use client";

import { useState } from "react";
import { LoaderCircle, Save, Sparkles, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import type { PriceItem } from "@/lib/api";

const API_URL = "/api/beoos";
const inputClass = "w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[#ed633f]/25";

function customFieldsText(fields: PriceItem["custom_fields"]) {
  return Object.entries(fields ?? {}).map(([key, value]) => `${key}=${String(value ?? "")}`).join("\n");
}

function parseCustomFields(value: string) {
  const fields: Record<string, string | number | boolean | null> = {};
  for (const line of value.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || !trimmed.includes("=")) continue;
    const [key, ...rest] = trimmed.split("=");
    const cleanKey = key.trim().toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "");
    if (!cleanKey) continue;
    const rawValue = rest.join("=").trim();
    if (rawValue === "true") fields[cleanKey] = true;
    else if (rawValue === "false") fields[cleanKey] = false;
    else if (rawValue !== "" && !Number.isNaN(Number(rawValue))) fields[cleanKey] = Number(rawValue);
    else fields[cleanKey] = rawValue;
  }
  return fields;
}

function payloadFromForm(form: FormData) {
  const min = String(form.get("amount_min") ?? "").trim();
  const max = String(form.get("amount_max") ?? "").trim();
  const stock = String(form.get("stock_quantity") ?? "").trim();
  return {
    service: String(form.get("service") ?? "").trim(),
    label: String(form.get("label") ?? "").trim(),
    amount_min: min ? Number(min) : null,
    amount_max: max ? Number(max) : null,
    currency: String(form.get("currency") ?? "NGN").trim().toUpperCase() || "NGN",
    stock_quantity: stock ? Number(stock) : null,
    custom_fields: parseCustomFields(String(form.get("custom_fields") ?? "")),
    source_url: String(form.get("source_url") ?? "").trim(),
  };
}

export function PriceCatalogueManager({
  businessId,
  prices,
}: {
  businessId: string;
  prices: PriceItem[];
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [importText, setImportText] = useState("");

  async function request(path: string, init: RequestInit) {
    const response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init.headers,
      },
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail ?? `Request failed (${response.status})`);
    }
    return response;
  }

  async function create(formData: FormData) {
    setBusy("new");
    setMessage(null);
    try {
      await request(`/businesses/${businessId}/prices`, {
        method: "POST",
        body: JSON.stringify(payloadFromForm(formData)),
      });
      setMessage("Catalogue item added.");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not add item.");
    } finally {
      setBusy(null);
    }
  }

  async function update(itemId: string, formData: FormData) {
    setBusy(itemId);
    setMessage(null);
    try {
      await request(`/businesses/${businessId}/prices/${itemId}`, {
        method: "PATCH",
        body: JSON.stringify(payloadFromForm(formData)),
      });
      setMessage("Catalogue item updated.");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not update item.");
    } finally {
      setBusy(null);
    }
  }

  async function deactivate(itemId: string) {
    if (!confirm("Deactivate this catalogue item?")) return;
    setBusy(itemId);
    setMessage(null);
    try {
      await fetch(`${API_URL}/businesses/${businessId}/prices/${itemId}`, {
        method: "DELETE",
      });
      setMessage("Catalogue item deactivated.");
      router.refresh();
    } catch {
      setMessage("Could not deactivate item.");
    } finally {
      setBusy(null);
    }
  }

  async function importItems() {
    setBusy("import");
    setMessage(null);
    try {
      const response = await request(`/businesses/${businessId}/prices/import-text`, {
        method: "POST",
        body: JSON.stringify({ text: importText }),
      });
      const result = await response.json() as { created: number };
      setImportText("");
      setMessage(`${result.created} catalogue item${result.created === 1 ? "" : "s"} imported.`);
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not import catalogue items.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mt-7 space-y-5">
      <div className="rounded-2xl border bg-white p-5">
        <div className="flex items-start gap-3">
          <Sparkles className="mt-1 size-5 text-[#ed633f]" />
          <div>
            <h2 className="font-bold">AI assistant import pad</h2>
            <p className="mt-1 text-sm text-[#747973]">
              Paste products/services line by line. Format: service | item | price | qty 10 | size=A4 | medium=pencil
            </p>
          </div>
        </div>
        <textarea
          className={`${inputClass} mt-4 min-h-32`}
          value={importText}
          onChange={(event) => setImportText(event.target.value)}
          placeholder={"portrait | 16x20 pencil portrait | 85000 | size=16x20 | medium=pencil\nart_supplies | Acrylic paint set | 25000 | qty 12 | brand=Winsor"}
        />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button type="button" onClick={importItems} disabled={busy === "import" || !importText.trim()}>
            {busy === "import" ? <LoaderCircle className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
            Import items
          </Button>
          {message && <p className="text-xs text-[#747973]">{message}</p>}
        </div>
      </div>

      <form action={create} className="grid gap-3 rounded-2xl border bg-[#fbfaf7] p-5 md:grid-cols-6">
        <input className={inputClass} name="service" placeholder="service e.g. portrait" required />
        <input className="md:col-span-2 w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[#ed633f]/25" name="label" placeholder="item/package name" required />
        <input className={inputClass} name="amount_min" placeholder="price" type="number" min="0" />
        <input className={inputClass} name="stock_quantity" placeholder="stock qty" type="number" min="0" />
        <Button type="submit" disabled={busy === "new"}>{busy === "new" ? "Saving..." : "Add item"}</Button>
        <textarea className={`${inputClass} md:col-span-6`} name="custom_fields" placeholder={"Optional custom fields, one per line:\nsize=16x20\nmedium=pencil\ncolor=blue"} />
        <input type="hidden" name="currency" value="NGN" />
        <input type="hidden" name="source_url" value="" />
      </form>

      <div className="space-y-4">
        {prices.map((item) => (
          <form key={item.id} action={(formData) => update(item.id, formData)} className="rounded-2xl border bg-white p-5">
            <div className="grid gap-3 md:grid-cols-6">
              <input className={inputClass} name="service" defaultValue={item.service} />
              <input className={`${inputClass} md:col-span-2`} name="label" defaultValue={item.label} />
              <input className={inputClass} name="amount_min" defaultValue={item.amount_min ?? ""} type="number" min="0" />
              <input className={inputClass} name="amount_max" defaultValue={item.amount_max ?? ""} type="number" min="0" placeholder="max/custom" />
              <input className={inputClass} name="stock_quantity" defaultValue={item.stock_quantity ?? ""} type="number" min="0" placeholder="stock" />
              <textarea className={`${inputClass} md:col-span-6`} name="custom_fields" defaultValue={customFieldsText(item.custom_fields)} />
              <input type="hidden" name="currency" value={item.currency || "NGN"} />
              <input type="hidden" name="source_url" value={item.source_url || ""} />
            </div>
            <div className="mt-3 flex justify-end gap-3">
              <Button type="button" variant="outline" onClick={() => deactivate(item.id)} disabled={busy === item.id}>
                <Trash2 className="size-4" /> Deactivate
              </Button>
              <Button type="submit" disabled={busy === item.id}>
                {busy === item.id ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}
                Save
              </Button>
            </div>
          </form>
        ))}
      </div>
    </div>
  );
}

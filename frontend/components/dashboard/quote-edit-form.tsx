"use client";

import { useState } from "react";
import { LoaderCircle, Save } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import type { Quote } from "@/lib/api";

const API_URL = "/api/beoos";

function stringValue(value: unknown, fallback = "") {
  return typeof value === "string" ? value : fallback;
}

export function QuoteEditForm({ businessId, quote }: { businessId: string; quote: Quote }) {
  const router = useRouter();
  const dimensions = quote.input_data.dimensions as { width?: string; height?: string; unit?: string } | undefined;
  const [projectLocation, setProjectLocation] = useState(stringValue(quote.input_data.project_location));
  const [deadline, setDeadline] = useState(stringValue(quote.input_data.deadline));
  const [width, setWidth] = useState(stringValue(dimensions?.width, "16"));
  const [height, setHeight] = useState(stringValue(dimensions?.height, "7"));
  const [paymentTerms, setPaymentTerms] = useState(stringValue(quote.input_data.payment_terms));
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function save() {
    setLoading(true);
    setMessage(null);
    const inputData = {
      ...quote.input_data,
      project_location: projectLocation,
      deadline,
      payment_terms: paymentTerms,
      dimensions: { ...(dimensions ?? {}), width, height, unit: dimensions?.unit ?? "ft" },
    };
    try {
      const response = await fetch(`${API_URL}/businesses/${businessId}/quotes/${quote.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: quote.title,
          status: quote.status,
          input_data: inputData,
          valid_until: quote.valid_until,
          internal_notes: quote.internal_notes,
        }),
      });
      if (!response.ok) throw new Error("Quote could not be saved.");
      setMessage("Quote updated.");
      router.refresh();
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Quote could not be saved.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-xs font-bold text-[#5f655f]">
          Width ft
          <input className="mt-1 w-full rounded-xl border px-3 py-2 text-sm" value={width} onChange={(event) => setWidth(event.target.value)} />
        </label>
        <label className="text-xs font-bold text-[#5f655f]">
          Height ft
          <input className="mt-1 w-full rounded-xl border px-3 py-2 text-sm" value={height} onChange={(event) => setHeight(event.target.value)} />
        </label>
      </div>
      <label className="block text-xs font-bold text-[#5f655f]">
        Project location
        <input className="mt-1 w-full rounded-xl border px-3 py-2 text-sm" value={projectLocation} onChange={(event) => setProjectLocation(event.target.value)} />
      </label>
      <label className="block text-xs font-bold text-[#5f655f]">
        Deadline
        <input className="mt-1 w-full rounded-xl border px-3 py-2 text-sm" value={deadline} onChange={(event) => setDeadline(event.target.value)} />
      </label>
      <label className="block text-xs font-bold text-[#5f655f]">
        Payment terms
        <textarea className="mt-1 min-h-20 w-full rounded-xl border px-3 py-2 text-sm" value={paymentTerms} onChange={(event) => setPaymentTerms(event.target.value)} />
      </label>
      <Button onClick={save} disabled={loading} className="w-full">
        {loading ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}
        Save quote changes
      </Button>
      {message && <p className="text-xs text-[#747973]">{message}</p>}
    </div>
  );
}

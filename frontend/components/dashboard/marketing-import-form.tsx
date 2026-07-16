"use client";

import { useState } from "react";
import { LoaderCircle, UploadCloud } from "lucide-react";
import { useRouter } from "next/navigation";
import type { MarketingImportResponse, MarketingSource } from "@/lib/api";

const API_URL = "/api/beoos";

const sampleRows = JSON.stringify(
  {
    source: "search_console",
    rows: [
      {
        page_url: "https://example.com/portrait-pricing",
        query: "portrait painting price in lagos",
        title: "Portrait Pricing",
        impressions: 240,
        clicks: 6,
        ctr: 0.025,
        average_position: 9.4,
      },
    ],
  },
  null,
  2,
);

export function MarketingImportForm({ businessId }: { businessId: string }) {
  const router = useRouter();
  const [source, setSource] = useState<MarketingSource>("search_console");
  const [payload, setPayload] = useState(sampleRows);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<MarketingImportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setResult(null);
    setError(null);
    try {
      const parsed = JSON.parse(payload);
      const body = Array.isArray(parsed) ? { source, rows: parsed } : { source, ...parsed };
      const response = await fetch(`${API_URL}/businesses/${businessId}/marketing/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail ?? `Import failed (${response.status})`);
      }
      const data = (await response.json()) as MarketingImportResponse;
      setResult(data);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not import marketing data");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-2xl border bg-white p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="font-bold">Import marketing signals</h2>
          <p className="mt-1 text-sm leading-6 text-[#747973]">
            Paste exported rows from Search Console, Blogger, Clarity, or your own website tracking.
            Later, these same fields will be filled by OAuth/API connectors.
          </p>
        </div>
        <select
          value={source}
          onChange={(event) => setSource(event.target.value as MarketingSource)}
          className="rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[#ed633f]/25"
        >
          <option value="search_console">Search Console</option>
          <option value="blogger">Blogger</option>
          <option value="clarity">Microsoft Clarity</option>
          <option value="website">Website/forms</option>
          <option value="manual">Manual</option>
        </select>
      </div>

      <textarea
        value={payload}
        onChange={(event) => setPayload(event.target.value)}
        className="mt-4 min-h-56 w-full rounded-2xl border bg-[#fbfaf7] p-4 font-mono text-xs leading-5 outline-none focus:ring-2 focus:ring-[#ed633f]/25"
        spellCheck={false}
      />

      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs leading-5 text-[#747973]">
          Accepted fields: page_url, query, title, impressions, clicks, ctr, average_position,
          sessions, leads, engagement_rate, scroll_depth, avg_time_seconds.
        </p>
        <button
          onClick={submit}
          disabled={busy}
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-[#ed633f] px-4 py-2.5 text-sm font-bold text-white transition hover:bg-[#d95836] disabled:opacity-60"
        >
          {busy ? <LoaderCircle className="size-4 animate-spin" /> : <UploadCloud className="size-4" />}
          Import signals
        </button>
      </div>

      {result && (
        <p className="mt-3 rounded-xl bg-green-50 px-4 py-3 text-sm font-semibold text-green-800">
          Imported {result.rows_created} row(s); skipped {result.duplicates_skipped} duplicate(s).
        </p>
      )}
      {error && (
        <p className="mt-3 rounded-xl bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}

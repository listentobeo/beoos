"use client";

import { CheckCircle2, LoaderCircle, PlugZap, Search, TriangleAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { MarketingConnectionStatus, MarketingConnectionSettings } from "@/lib/api";

const API_URL = "/api/beoos";

const inputClass =
  "w-full rounded-2xl border bg-white px-4 py-3 text-sm outline-none transition focus:ring-2 focus:ring-[#ed633f]/20";

export function MarketingConnectionPanel({
  businessId,
  status,
}: {
  businessId: string;
  status: MarketingConnectionStatus;
}) {
  const router = useRouter();
  const [draft, setDraft] = useState<MarketingConnectionSettings>(status.settings);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  function setField<K extends keyof MarketingConnectionSettings>(
    key: K,
    value: MarketingConnectionSettings[K],
  ) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  async function save() {
    setSaving(true);
    setMessage(null);
    try {
      const response = await fetch(`${API_URL}/businesses/${businessId}/marketing/connections`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail ?? `Could not save marketing setup (${response.status})`);
      setMessage("Marketing setup saved.");
      router.refresh();
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Could not save marketing setup.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-[28px] border bg-white p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="grid size-11 place-items-center rounded-2xl bg-orange-50 text-[#ed633f]">
              <PlugZap className="size-5" />
            </div>
            <div>
              <h2 className="text-lg font-black tracking-[-0.03em]">Marketing connector setup</h2>
              <p className="text-sm leading-6 text-[#747973]">
                Save the tenant’s website identity now. Once API keys/OAuth are connected, these
                same values power Search Console, Blogger, and Clarity pulls.
              </p>
            </div>
          </div>
        </div>
        <Button onClick={save} disabled={saving} className="bg-[#ed633f] text-white hover:bg-[#d95836]">
          {saving ? <LoaderCircle className="size-4 animate-spin" /> : <CheckCircle2 className="size-4" />}
          Save setup
        </Button>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2">
        <input
          className={inputClass}
          value={draft.website_url}
          onChange={(event) => setField("website_url", event.target.value)}
          placeholder="Website URL e.g. https://beoarts.com"
        />
        <input
          className={inputClass}
          value={draft.search_console_property_url}
          onChange={(event) => setField("search_console_property_url", event.target.value)}
          placeholder="Search Console property URL"
        />
        <input
          className={inputClass}
          value={draft.blogger_blog_id}
          onChange={(event) => setField("blogger_blog_id", event.target.value)}
          placeholder="Blogger blog ID"
        />
        <input
          className={inputClass}
          value={draft.clarity_project_id}
          onChange={(event) => setField("clarity_project_id", event.target.value)}
          placeholder="Microsoft Clarity project ID"
        />
        <textarea
          className={`${inputClass} min-h-24 md:col-span-2`}
          value={draft.content_goals}
          onChange={(event) => setField("content_goals", event.target.value)}
          placeholder="Content goals e.g. more mural leads, portrait enquiries, art school signups"
        />
        <input
          className={`${inputClass} md:col-span-2`}
          value={draft.target_locations}
          onChange={(event) => setField("target_locations", event.target.value)}
          placeholder="Target locations e.g. Lagos, Abuja, Nigeria, UK diaspora"
        />
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-4">
        {status.providers.map((provider) => (
          <div key={provider.key} className="rounded-2xl border bg-[#fbfaf7] p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-white text-[#ed633f]">
                <Search className="size-4" />
              </div>
              <Badge className={provider.connected ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-700"}>
                {provider.connected ? "ready" : provider.configured ? "needs tenant info" : "needs keys"}
              </Badge>
            </div>
            <h3 className="mt-3 font-black">{provider.label}</h3>
            <p className="mt-2 text-xs leading-5 text-[#747973]">{provider.notes}</p>
            {provider.setup_required.length > 0 && (
              <div className="mt-3 rounded-xl bg-white p-3 text-xs leading-5 text-[#6b7280]">
                <p className="mb-1 flex items-center gap-1 font-bold text-amber-700">
                  <TriangleAlert className="size-3" /> Missing
                </p>
                {provider.setup_required.map((item) => (
                  <p key={item}>• {item}</p>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {message && <p className="mt-4 rounded-2xl bg-[#f7f6f2] p-3 text-sm font-semibold text-[#5f655f]">{message}</p>}
    </div>
  );
}

"use client";

import { BellRing, LoaderCircle, MailCheck, Send } from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import type { DailyReportPreview, DailyReportSettings } from "@/lib/api";

const API_URL = "/api/beoos";

function money(value: string) {
  const amount = Number(value);
  if (!Number.isFinite(amount) || amount <= 0) return "₦0";
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: "NGN",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function DailyReportSettingsCard({
  businessId,
  initialSettings,
  initialPreview,
}: {
  businessId: string;
  initialSettings: DailyReportSettings;
  initialPreview: DailyReportPreview | null;
}) {
  const [settings, setSettings] = useState(initialSettings);
  const [preview, setPreview] = useState(initialPreview);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const compactStats = useMemo(() => {
    if (!preview) return [];
    return [
      ["Messages", preview.totals.inbound_messages],
      ["Approvals", preview.totals.needs_approval],
      ["Leads", preview.totals.leads_created],
      ["Quotes", preview.totals.quotes_created],
      ["Follow-ups", preview.totals.followups_due],
    ];
  }, [preview]);

  async function saveSettings() {
    setLoading(true);
    setMessage(null);
    try {
      const response = await fetch(`${API_URL}/businesses/${businessId}/reports/daily/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled: settings.enabled,
          time: settings.time,
          timezone: settings.timezone,
          email: settings.email,
          push_enabled: settings.push_enabled,
        }),
      });
      if (!response.ok) throw new Error(`Daily report settings could not be saved (${response.status}).`);
      setSettings((await response.json()) as DailyReportSettings);
      await refreshPreview();
      setMessage("Daily report settings saved.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Daily report settings could not be saved.");
    } finally {
      setLoading(false);
    }
  }

  async function refreshPreview() {
    const response = await fetch(`${API_URL}/businesses/${businessId}/reports/daily/preview`, {
      cache: "no-store",
    });
    if (!response.ok) throw new Error(`Daily report preview could not load (${response.status}).`);
    setPreview((await response.json()) as DailyReportPreview);
  }

  async function sendTest() {
    setLoading(true);
    setMessage(null);
    try {
      const response = await fetch(`${API_URL}/businesses/${businessId}/reports/daily/send-test`, {
        method: "POST",
      });
      if (!response.ok) throw new Error(`Test report could not be sent (${response.status}).`);
      const result = (await response.json()) as {
        success: boolean;
        email_sent: boolean;
        push_sent: number;
        message: string;
        preview: DailyReportPreview;
      };
      setPreview(result.preview);
      setMessage(result.message);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Test report could not be sent.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-5 rounded-2xl border bg-[#fbfaf7] p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex items-start gap-3">
          <div className="grid size-10 place-items-center rounded-xl bg-[#fff0ea] text-[#ed633f]">
            <MailCheck className="size-4" />
          </div>
          <div>
            <h3 className="font-bold">Daily business report</h3>
            <p className="mt-1 text-sm leading-6 text-[#747973]">
              Get one end-of-day summary from inbox, WhatsApp, CRM, quotes, approvals, and follow-ups.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" onClick={sendTest} disabled={loading}>
            {loading ? <LoaderCircle className="size-4 animate-spin" /> : <Send className="size-4" />}
            Send test report
          </Button>
          <Button type="button" size="sm" onClick={saveSettings} disabled={loading}>
            {loading && <LoaderCircle className="size-4 animate-spin" />}
            Save report settings
          </Button>
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        <label className="rounded-2xl border bg-white p-3 text-sm">
          <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[#8b9089]">Status</span>
          <span className="mt-3 flex items-center gap-2">
            <input
              type="checkbox"
              checked={settings.enabled}
              onChange={(event) => setSettings({ ...settings, enabled: event.target.checked })}
            />
            Send daily report
          </span>
        </label>
        <label className="rounded-2xl border bg-white p-3 text-sm">
          <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[#8b9089]">Time</span>
          <input
            className="mt-2 w-full rounded-xl border px-3 py-2"
            type="time"
            value={settings.time}
            onChange={(event) => setSettings({ ...settings, time: event.target.value })}
          />
        </label>
        <label className="rounded-2xl border bg-white p-3 text-sm">
          <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[#8b9089]">Timezone</span>
          <input
            className="mt-2 w-full rounded-xl border px-3 py-2"
            value={settings.timezone}
            onChange={(event) => setSettings({ ...settings, timezone: event.target.value })}
            placeholder="Africa/Lagos"
          />
        </label>
        <label className="rounded-2xl border bg-white p-3 text-sm">
          <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[#8b9089]">Push</span>
          <span className="mt-3 flex items-center gap-2">
            <input
              type="checkbox"
              checked={settings.push_enabled}
              onChange={(event) => setSettings({ ...settings, push_enabled: event.target.checked })}
            />
            Device alert too
          </span>
        </label>
      </div>

      <label className="mt-3 block rounded-2xl border bg-white p-3 text-sm">
        <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[#8b9089]">Report recipient</span>
        <input
          className="mt-2 w-full rounded-xl border px-3 py-2"
          type="email"
          value={settings.email ?? ""}
          onChange={(event) => setSettings({ ...settings, email: event.target.value })}
          placeholder="owner@example.com"
        />
      </label>

      {preview && (
        <div className="mt-5 rounded-2xl border bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#8b9089]">Today’s preview</p>
              <h4 className="mt-1 font-bold">{preview.subject}</h4>
              <p className="mt-1 text-xs text-[#747973]">Recipient: {preview.recipient}</p>
            </div>
            <p className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
              <BellRing className="size-3.5" />
              {settings.enabled ? "Scheduled" : "Not scheduled"}
            </p>
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-5">
            {compactStats.map(([label, value]) => (
              <div key={label} className="rounded-xl bg-[#f7f6f2] p-3">
                <p className="text-lg font-black">{value}</p>
                <p className="text-xs text-[#747973]">{label}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div>
              <p className="text-sm font-bold">Recommended actions</p>
              <ul className="mt-2 space-y-1 text-sm text-[#747973]">
                {preview.action_items.map((item) => (
                  <li key={item}>• {item}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-sm font-bold">Value snapshot</p>
              <p className="mt-2 text-sm text-[#747973]">Open quote value: {money(preview.totals.open_quote_value)}</p>
              <p className="text-sm text-[#747973]">Accepted quote value: {money(preview.totals.accepted_quote_value)}</p>
            </div>
          </div>
        </div>
      )}

      {message && <p className="mt-3 text-xs text-[#747973]">{message}</p>}
      {settings.last_sent_at && (
        <p className="mt-2 text-xs text-[#9a9f98]">Last sent: {new Date(settings.last_sent_at).toLocaleString()}</p>
      )}
    </div>
  );
}

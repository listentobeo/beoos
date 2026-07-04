"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";
import type { BusinessWhatsAppSettings } from "@/lib/api";

const inputClass = "w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[#ed633f]/25";
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export function WhatsAppSettingsForm({
  businessId,
  settings,
}: {
  businessId: string;
  settings: BusinessWhatsAppSettings;
}) {
  const { getToken } = useAuth();
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function save(formData: FormData) {
    setSaving(true);
    setMessage(null);
    const payload: BusinessWhatsAppSettings = {
      enabled: formData.get("enabled") === "on",
      phone_number_id: String(formData.get("phone_number_id") ?? "").trim(),
      business_account_id: String(formData.get("business_account_id") ?? "").trim(),
      display_phone_number: String(formData.get("display_phone_number") ?? "").trim(),
    };
    try {
      const token = await getToken();
      const response = await fetch(`${API_URL}/businesses/${businessId}/whatsapp`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(`Save failed (${response.status}).`);
      setMessage("WhatsApp settings saved.");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form action={save} className="mt-5 grid gap-3">
      <label className="flex items-start gap-3 rounded-xl bg-[#f7f6f2] p-3 text-sm">
        <input name="enabled" type="checkbox" defaultChecked={settings.enabled} className="mt-1" />
        <span>
          <span className="block font-semibold">Enable WhatsApp Cloud API for this business</span>
          <span className="text-[#777c76]">Inbound webhooks will create inbox threads for this tenant.</span>
        </span>
      </label>
      <label className="text-xs font-semibold text-[#646a64]">
        Meta phone number ID
        <input className={`${inputClass} mt-1.5`} name="phone_number_id" defaultValue={settings.phone_number_id} placeholder="e.g. 123456789012345" />
      </label>
      <label className="text-xs font-semibold text-[#646a64]">
        WhatsApp Business Account ID
        <input className={`${inputClass} mt-1.5`} name="business_account_id" defaultValue={settings.business_account_id} placeholder="Optional but useful for audits" />
      </label>
      <label className="text-xs font-semibold text-[#646a64]">
        Display phone number
        <input className={`${inputClass} mt-1.5`} name="display_phone_number" defaultValue={settings.display_phone_number} placeholder="+234..." />
      </label>
      <div className="rounded-xl border border-dashed bg-white p-3 text-xs leading-5 text-[#777c76]">
        Webhook callback:
        <code className="mt-1 block break-all rounded-lg bg-[#f7f6f2] p-2 text-[#262a31]">
          {API_URL.replace(/\/api\/v1$/, "")}/api/v1/webhooks/whatsapp
        </code>
      </div>
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={saving} size="sm">{saving ? "Saving..." : "Save WhatsApp settings"}</Button>
        {message && <p className="text-xs text-[#747973]">{message}</p>}
      </div>
    </form>
  );
}

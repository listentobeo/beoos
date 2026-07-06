"use client";

import { FormEvent, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { LoaderCircle, Save } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import type { Business } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const inputClass = "h-10 w-full rounded-xl border bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-[#ed633f]/25";
const textareaClass = "min-h-24 w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[#ed633f]/25";

export function BusinessProfileForm({ business }: { business: Business }) {
  const { getToken } = useAuth();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = {
      name: String(form.get("name") ?? "").trim(),
      primary_email: String(form.get("primary_email") ?? "").trim(),
      whatsapp_number: String(form.get("whatsapp_number") ?? "").trim(),
      timezone: String(form.get("timezone") ?? "").trim() || "Africa/Lagos",
      reply_signature: String(form.get("reply_signature") ?? "").trim(),
    };
    setLoading(true);
    setMessage(null);
    try {
      const token = await getToken();
      const response = await fetch(`${API_URL}/businesses/${business.id}/profile`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        let detail = "";
        try {
          const error = (await response.json()) as { detail?: string };
          detail = error.detail ? ` ${error.detail}` : "";
        } catch {}
        throw new Error(`Business profile could not be saved.${detail}`);
      }
      setMessage("Business profile saved.");
      router.refresh();
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Business profile could not be saved");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-5 grid gap-3 sm:grid-cols-2">
      <label className="text-xs font-semibold text-[#646a64]">
        Business name
        <input className={`${inputClass} mt-1.5`} name="name" defaultValue={business.name} required />
      </label>
      <label className="text-xs font-semibold text-[#646a64]">
        Primary email
        <input className={`${inputClass} mt-1.5`} name="primary_email" type="email" defaultValue={business.primary_email} required />
      </label>
      <label className="text-xs font-semibold text-[#646a64]">
        WhatsApp number
        <input className={`${inputClass} mt-1.5`} name="whatsapp_number" defaultValue={business.whatsapp_number} required />
      </label>
      <label className="text-xs font-semibold text-[#646a64]">
        Timezone
        <input className={`${inputClass} mt-1.5`} name="timezone" defaultValue={business.timezone || "Africa/Lagos"} required />
      </label>
      <label className="text-xs font-semibold text-[#646a64] sm:col-span-2">
        Reply signature
        <textarea className={`${textareaClass} mt-1.5`} name="reply_signature" defaultValue={business.reply_signature} required />
      </label>
      <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
        <Button type="submit" disabled={loading}>
          {loading ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}
          Save business profile
        </Button>
        {message && <p className="text-xs text-[#676d67]">{message}</p>}
      </div>
    </form>
  );
}

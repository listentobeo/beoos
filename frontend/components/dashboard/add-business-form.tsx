"use client";

import { FormEvent, useState } from "react";
import { Building2, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

const inputClass = "h-10 w-full rounded-xl border bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-[#ed633f]/25";

export function AddBusinessForm() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    setLoading(true);
    setMessage(null);
    const form = new FormData(formElement);
    const name = String(form.get("name") ?? "").trim();
    const payload = {
      name,
      slug: name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""),
      primary_email: String(form.get("email") ?? "").trim(),
      whatsapp_number: String(form.get("whatsapp") ?? "").trim(),
      reply_signature: String(form.get("signature") ?? "").trim(),
    };
    try {
      const apiUrl = "/api/beoos";
      const response = await fetch(`${apiUrl}/businesses`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const error = await response.json().catch(() => null) as { detail?: unknown } | null;
        const detail = typeof error?.detail === "string" ? ` ${error.detail}` : "";
        throw new Error(`Could not create this business profile (${response.status}).${detail}`);
      }
      const created = (await response.json()) as { id: string };
      document.cookie = `beoos_business_id=${encodeURIComponent(created.id)}; path=/; max-age=31536000; samesite=lax`;
      formElement.reset();
      setMessage("Business profile created.");
      router.refresh();
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Could not create this business profile");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-5 grid gap-3 sm:grid-cols-2">
      <label className="text-xs font-semibold text-[#646a64]">Business name<input className={`${inputClass} mt-1.5`} name="name" required /></label>
      <label className="text-xs font-semibold text-[#646a64]">Primary email<input className={`${inputClass} mt-1.5`} name="email" type="email" required /></label>
      <label className="text-xs font-semibold text-[#646a64]">WhatsApp number<input className={`${inputClass} mt-1.5`} name="whatsapp" required /></label>
      <label className="text-xs font-semibold text-[#646a64]">Reply signature<input className={`${inputClass} mt-1.5`} name="signature" required /></label>
      <div className="flex items-center gap-3 sm:col-span-2">
        <Button type="submit" disabled={loading}>{loading ? <LoaderCircle className="size-4 animate-spin" /> : <Building2 className="size-4" />}Add business</Button>
        {message && <p className="text-xs text-[#676d67]">{message}</p>}
      </div>
    </form>
  );
}

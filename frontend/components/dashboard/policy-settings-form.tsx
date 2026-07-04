"use client";

import { FormEvent, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { LoaderCircle, Save } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import type { BusinessAIPolicy } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const inputClass = "rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[#ed633f]/25";

function readCheckbox(form: FormData, name: keyof BusinessAIPolicy) {
  return form.get(name) === "on";
}

export function PolicySettingsForm({
  businessId,
  policy,
}: {
  businessId: string;
  policy: BusinessAIPolicy;
}) {
  const { getToken } = useAuth();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload: BusinessAIPolicy = {
      auto_acknowledge: readCheckbox(form, "auto_acknowledge"),
      auto_route_whatsapp: readCheckbox(form, "auto_route_whatsapp"),
      confidence_threshold: Number(form.get("confidence_threshold") || policy.confidence_threshold),
      require_approval_for_prices: readCheckbox(form, "require_approval_for_prices"),
      require_approval_for_commitments: readCheckbox(form, "require_approval_for_commitments"),
      require_approval_for_risk_flags: readCheckbox(form, "require_approval_for_risk_flags"),
      existing_clients_stay_on_current_channel: readCheckbox(form, "existing_clients_stay_on_current_channel"),
      art_school_stays_in_email: readCheckbox(form, "art_school_stays_in_email"),
      professionals_stay_in_email: readCheckbox(form, "professionals_stay_in_email"),
      route_only_deals_to_whatsapp: readCheckbox(form, "route_only_deals_to_whatsapp"),
      custom_instructions: String(form.get("custom_instructions") ?? "").trim(),
    };

    setLoading(true);
    setMessage(null);
    try {
      const token = await getToken();
      const response = await fetch(`${API_URL}/businesses/${businessId}/policy`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error("Policy could not be saved");
      setMessage("Business AI policy saved.");
      router.refresh();
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Policy could not be saved");
    } finally {
      setLoading(false);
    }
  }

  const checks: Array<[keyof BusinessAIPolicy, string, string]> = [
    ["auto_acknowledge", "Allow automatic acknowledgements", "Safe contextual replies can send immediately."],
    ["auto_route_whatsapp", "Allow WhatsApp routing", "Only when the policy and AI agree it is a new deal."],
    ["require_approval_for_prices", "Prices need approval", "Blocks any draft containing price or currency amounts."],
    ["require_approval_for_commitments", "Commitments need approval", "Blocks final deadlines, guarantees, refunds, discounts, and contract language."],
    ["require_approval_for_risk_flags", "Risk flags need approval", "Money, complaint, legal, payment, discount, contract, or refund requests wait for you."],
    ["existing_clients_stay_on_current_channel", "Existing clients stay on current channel", "Prevents pushing existing clients to WhatsApp."],
    ["art_school_stays_in_email", "Art School stays in email", "Keeps school enquiries in the inbox."],
    ["professionals_stay_in_email", "Professionals stay in email", "Corporate and professional enquiries remain email-first."],
    ["route_only_deals_to_whatsapp", "Only real deals go to WhatsApp", "General questions and weak leads stay in email."],
  ];

  return (
    <form onSubmit={submit} className="mt-5 space-y-5">
      <div>
        <label className="text-xs font-semibold text-[#646a64]" htmlFor="confidence_threshold">
          Auto-send confidence threshold
        </label>
        <input
          id="confidence_threshold"
          name="confidence_threshold"
          type="number"
          min="0.5"
          max="1"
          step="0.01"
          defaultValue={policy.confidence_threshold}
          className={`${inputClass} mt-1.5 w-full sm:w-48`}
        />
        <p className="mt-1 text-xs text-[#858a84]">Higher is safer. Beo Art Studio currently uses 0.90.</p>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {checks.map(([name, label, help]) => (
          <label key={name} className="rounded-2xl border bg-[#fbfaf7] p-4 text-sm">
            <span className="flex items-start gap-3">
              <input name={name} type="checkbox" defaultChecked={Boolean(policy[name])} className="mt-1 size-4 accent-[#ed633f]" />
              <span>
                <span className="block font-semibold text-[#252a33]">{label}</span>
                <span className="mt-1 block text-xs leading-5 text-[#747973]">{help}</span>
              </span>
            </span>
          </label>
        ))}
      </div>

      <div>
        <label className="text-xs font-semibold text-[#646a64]" htmlFor="custom_instructions">
          Business-specific AI instructions
        </label>
        <textarea
          id="custom_instructions"
          name="custom_instructions"
          rows={5}
          maxLength={2000}
          defaultValue={policy.custom_instructions}
          className={`${inputClass} mt-1.5 w-full resize-y leading-6`}
          placeholder="Example: Service pages are authoritative. Do not quote blog prices. Route only new portrait/mural deals to WhatsApp."
        />
        <p className="mt-1 text-xs text-[#858a84]">This is passed into the AI prompt for this business only.</p>
      </div>

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={loading}>
          {loading ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}
          Save policy
        </Button>
        {message && <p className="text-xs text-[#676d67]">{message}</p>}
      </div>
    </form>
  );
}

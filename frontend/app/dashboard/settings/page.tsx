import { CheckCircle2, Mail, MessageCircleMore, ShieldCheck } from "lucide-react";
import { AddBusinessForm } from "@/components/dashboard/add-business-form";
import { PolicySettingsForm } from "@/components/dashboard/policy-settings-form";
import { WebsiteFormCard } from "@/components/dashboard/website-form-card";
import { ZohoConnectButton } from "@/components/dashboard/zoho-connect-button";
import { Card } from "@/components/ui/card";
import { activeBusiness, beoApi, type BusinessAIPolicy, type MailboxStatus } from "@/lib/api";

export const metadata = { title: "Business settings" };

export default async function SettingsPage() {
  let businessId: string | null = null;
  let businessSlug = "";
  let businessName = "Current business";
  let websiteFormKey = "";
  let primaryEmail = "Not configured";
  let whatsappNumber = "Not configured";
  let replySignature = "Not configured";
  let aiPolicy: BusinessAIPolicy | null = null;
  let mailbox: MailboxStatus | null = null;
  let setupMessage = "Initial business setup has not completed.";

  try {
    const business = await activeBusiness();
    businessId = business?.id ?? null;
    businessSlug = business?.slug ?? "";
    businessName = business?.name ?? businessName;
    websiteFormKey = business?.website_form_key ?? "";
    primaryEmail = business?.primary_email ?? primaryEmail;
    whatsappNumber = business?.whatsapp_number ?? whatsappNumber;
    replySignature = business?.reply_signature ?? replySignature;
    aiPolicy = business?.ai_policy ?? null;
    if (business) mailbox = await beoApi.mailbox(business.id);
  } catch {
    setupMessage = "Unable to load business data from the BeoOS API.";
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-5 md:px-8">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#90948f]">{businessName}</p>
      <h1 className="mt-1 text-2xl font-bold tracking-[-0.035em] sm:text-3xl">Business settings</h1>
      <p className="mt-2 text-sm text-[#747973]">Connections, reply policies, and channel rules for this business.</p>

      <div className="mt-7 grid gap-5 md:grid-cols-2">
        <Card className="p-5">
          <div className="flex items-start gap-3">
            <div className="grid size-10 place-items-center rounded-xl bg-[#fff0ea] text-[#ed633f]"><Mail className="size-4" /></div>
            <div>
              <h2 className="font-bold">Zoho Mail</h2>
              <p className="mt-1 text-sm text-[#777c76]">{primaryEmail} · one-year history</p>
              {mailbox?.connected && (
                <p className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                  <CheckCircle2 className="size-3.5" /> Connected
                </p>
              )}
            </div>
          </div>
          <div className="mt-5">
            {businessId ? <ZohoConnectButton businessId={businessId} /> : <p className="text-sm text-amber-700">{setupMessage}</p>}
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-start gap-3">
            <div className="grid size-10 place-items-center rounded-xl bg-emerald-50 text-emerald-700"><MessageCircleMore className="size-4" /></div>
            <div>
              <h2 className="font-bold">WhatsApp handoff</h2>
              <p className="mt-1 text-sm text-[#777c76]">{whatsappNumber}</p>
            </div>
          </div>
          <p className="mt-5 flex items-center gap-2 text-sm text-[#535953]"><CheckCircle2 className="size-4 text-emerald-600" /> Only new deal opportunities</p>
        </Card>

        {businessSlug && (
          <WebsiteFormCard businessSlug={businessSlug} formKey={websiteFormKey} />
        )}

        <Card className="p-5 md:col-span-2">
          <div className="flex items-start gap-3">
            <div className="grid size-10 place-items-center rounded-xl bg-violet-50 text-violet-700"><ShieldCheck className="size-4" /></div>
            <div>
              <h2 className="font-bold">Automatic reply policy</h2>
              <p className="mt-1 whitespace-pre-line text-sm text-[#777c76]">Signed “{replySignature}”</p>
            </div>
          </div>
          <div className="mt-5 grid gap-3 text-sm sm:grid-cols-3">
            <p className="rounded-xl bg-[#f7f6f2] p-3">Immediate contextual acknowledgements</p>
            <p className="rounded-xl bg-[#f7f6f2] p-3">Existing clients stay on their channel</p>
            <p className="rounded-xl bg-[#f7f6f2] p-3">Prices and commitments need approval</p>
          </div>
        </Card>

        <Card className="p-5 md:col-span-2">
          <div className="flex items-start gap-3">
            <div className="grid size-10 place-items-center rounded-xl bg-violet-50 text-violet-700"><ShieldCheck className="size-4" /></div>
            <div>
              <h2 className="font-bold">Business AI policy</h2>
              <p className="mt-1 text-sm leading-6 text-[#777c76]">
                These rules belong to this business only. Core BeoOS guardrails still block unsafe actions, but this section controls how aggressive or careful the AI should be for {businessName}.
              </p>
            </div>
          </div>
          {businessId && aiPolicy ? (
            <PolicySettingsForm businessId={businessId} policy={aiPolicy} />
          ) : (
            <p className="mt-5 text-sm text-amber-700">{setupMessage}</p>
          )}
        </Card>

        <Card className="p-5 md:col-span-2">
          <h2 className="font-bold">Add another Beo business</h2>
          <p className="mt-1 text-sm text-[#777c76]">Each business receives isolated inboxes, contacts, prices, prompts, and analytics.</p>
          <AddBusinessForm />
        </Card>
      </div>
    </div>
  );
}

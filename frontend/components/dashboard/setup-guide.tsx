import { ArrowRight, Bell, Building2, Mail, MessageCircleMore, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { Card } from "@/components/ui/card";

const steps = [
  {
    title: "Create your business profile",
    body: "Add the business name, primary email, WhatsApp number, timezone, and reply signature BeoOS should use.",
    icon: Building2,
  },
  {
    title: "Connect your channels",
    body: "Bring Zoho Mail, Gmail, website forms, and WhatsApp into one tenant inbox.",
    icon: Mail,
  },
  {
    title: "Set AI policy",
    body: "Tell BeoOS what it can acknowledge, what needs approval, and when a lead should move to WhatsApp.",
    icon: ShieldCheck,
  },
  {
    title: "Enable alerts",
    body: "Turn on push and email alerts so new leads and approval requests do not sit unseen.",
    icon: Bell,
  },
] as const;

export function SetupGuide({
  title = "BeoOS has not identified your business yet",
  compact = false,
}: {
  title?: string;
  compact?: boolean;
}) {
  return (
    <Card className="border-[#ed633f]/20 bg-[#fffaf7] p-5">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#ed633f]">
            New workspace setup
          </p>
          <h2 className="mt-1 text-xl font-bold tracking-[-0.03em] text-[#171b23]">{title}</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[#6f746e]">
            Start in Business Settings. Once your business is created, BeoOS can connect your
            customer network, classify conversations, draft replies, create CRM leads, build quotes,
            and remind you to follow up.
          </p>
        </div>
        <Link
          href="/dashboard/settings#add-business"
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-[#ed633f] px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#d95836]"
        >
          Start business setup <ArrowRight className="size-4" />
        </Link>
      </div>

      {!compact && (
        <div className="mt-5 grid gap-3 md:grid-cols-4">
          {steps.map(({ title: stepTitle, body, icon: Icon }) => (
            <div key={stepTitle} className="rounded-2xl border bg-white p-4">
              <div className="grid size-9 place-items-center rounded-xl bg-[#fff0ea] text-[#ed633f]">
                <Icon className="size-4" />
              </div>
              <h3 className="mt-3 text-sm font-bold text-[#20242b]">{stepTitle}</h3>
              <p className="mt-1 text-xs leading-5 text-[#747973]">{body}</p>
            </div>
          ))}
        </div>
      )}

      <div className="mt-5 rounded-2xl bg-white p-4 text-sm leading-6 text-[#5f655f]">
        <div className="flex items-start gap-3">
          <MessageCircleMore className="mt-0.5 size-4 shrink-0 text-[#ed633f]" />
          <p>
            BeoOS is your unified business command center: inbox, CRM, AI assistant, quotes,
            follow-ups, and alerts per business tenant.
          </p>
        </div>
      </div>
    </Card>
  );
}

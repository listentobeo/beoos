import Link from "next/link";
import { PublicPageShell } from "@/components/public/site-shell";

export const metadata = {
  title: "How BeoOS Works",
  description:
    "Learn how BeoOS connects business channels, tenant policies, AI drafts, CRM leads, quotes, and approval workflows.",
};

const steps = [
  ["Add your business", "Create a tenant workspace with its own email, WhatsApp number, signature, pricing, policies, and contacts."],
  ["Connect channels", "Bring in Zoho Mail, Gmail, WhatsApp Cloud API, website forms, and future channel integrations."],
  ["Set AI policy", "Tell BeoOS how to acknowledge messages, when to draft replies, what needs approval, and where serious deals go."],
  ["Operate from one dashboard", "Review inboxes, leads, quotes, pricing, approvals, follow-ups, notifications, and analytics in one place."],
];

export default function HowItWorksPage() {
  return (
    <PublicPageShell>
      <section className="mx-auto max-w-5xl px-4 py-12 sm:px-5 sm:py-16">
        <p className="text-xs font-black uppercase tracking-[0.22em] text-[#ed633f] sm:text-sm">
          How it works
        </p>
        <h1 className="mt-3 max-w-4xl text-4xl font-black tracking-[-0.045em] text-[#101827] sm:text-6xl">
          Connect channels, set policy, and let BeoOS prepare the work.
        </h1>
        <div className="mt-10 grid gap-4">
          {steps.map(([title, text], index) => (
            <article key={title} className="flex gap-4 rounded-3xl border bg-white p-5 sm:p-6">
              <span className="grid size-10 shrink-0 place-items-center rounded-full bg-[#ed633f] font-black text-white">
                {index + 1}
              </span>
              <div>
                <h2 className="text-lg font-black sm:text-xl">{title}</h2>
                <p className="mt-2 text-sm leading-7 text-[#59605a] sm:text-base">{text}</p>
              </div>
            </article>
          ))}
        </div>
        <Link
          href="/sign-up"
          className="mt-10 inline-flex rounded-full bg-[#ed633f] px-6 py-3 font-black text-white"
        >
          Create BeoOS account
        </Link>
      </section>
    </PublicPageShell>
  );
}

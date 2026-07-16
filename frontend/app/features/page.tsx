import Link from "next/link";
import { PublicPageShell } from "@/components/public/site-shell";

export const metadata = {
  title: "Features",
  description:
    "Explore BeoOS features for unified inbox, AI lead qualification, WhatsApp, Gmail, Zoho Mail, CRM, quotations, pricing, approvals, and alerts.",
};

const features = [
  ["Unified inbox", "Bring Zoho Mail, Gmail, WhatsApp, and website form conversations into one tenant-aware workspace."],
  ["AI lead qualification", "Detect serious enquiries, score intent, draft replies, and route high-value opportunities for approval."],
  ["CRM pipeline", "Turn customer conversations into structured leads with service, budget, deadline, source, and follow-up context."],
  ["Quotations", "Create flexible branded quotes from leads, pricing catalogue data, and business-specific templates."],
  ["Pricing catalogue", "Store services, products, inventory-style quantities, custom fields, and pricing rules for each business."],
  ["Notifications", "Send alerts for new inbox activity, approval queues, follow-ups, and urgent customer requests."],
];

export default function FeaturesPage() {
  return (
    <PublicPageShell>
      <section className="mx-auto max-w-6xl px-4 py-12 sm:px-5 sm:py-16">
        <p className="text-xs font-black uppercase tracking-[0.22em] text-[#ed633f] sm:text-sm">
          BeoOS features
        </p>
        <h1 className="mt-3 max-w-4xl text-4xl font-black tracking-[-0.045em] text-[#101827] sm:text-6xl">
          One operating layer for customer communication and sales work.
        </h1>
        <p className="mt-5 max-w-3xl text-base leading-7 text-[#59605a] sm:text-lg sm:leading-8">
          BeoOS connects the channels where customers talk to your business with the workflows that
          turn those messages into leads, quotes, approvals, and follow-ups.
        </p>
        <div className="mt-10 grid gap-4 md:grid-cols-2">
          {features.map(([title, text]) => (
            <article key={title} className="rounded-3xl border bg-white p-5 sm:p-6">
              <h2 className="text-lg font-black sm:text-xl">{title}</h2>
              <p className="mt-3 text-sm leading-7 text-[#59605a] sm:text-base">{text}</p>
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

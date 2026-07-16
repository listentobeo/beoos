import Link from "next/link";
import { PublicPageShell } from "@/components/public/site-shell";

export const metadata = {
  title: "Pricing",
  description:
    "BeoOS launch pricing for Nigerian businesses: Starter, Growth, and Scale plans for AI-powered customer communication automation.",
};

const pricing = [
  {
    name: "Starter",
    price: "₦5,000",
    audience: "Solo operators and very small businesses",
    features: ["1 business workspace", "Unified inbox basics", "Website form intake", "AI drafts with approval", "Basic CRM leads"],
  },
  {
    name: "Growth",
    price: "₦15,000",
    audience: "Growing businesses with active customer conversations",
    highlighted: true,
    features: ["Up to 3 business workspaces", "Zoho/Gmail + WhatsApp workflows", "CRM pipeline and follow-ups", "Quotation and pricing catalogue", "Push and email alerts"],
  },
  {
    name: "Scale",
    price: "₦30,000",
    audience: "Larger teams managing multiple brands or branches",
    features: ["Up to 10 business workspaces", "Higher automation usage", "Multi-channel approval queues", "Advanced pricing/inventory workflows", "Priority setup support"],
  },
];

export default function PricingPage() {
  return (
    <PublicPageShell>
      <section className="mx-auto max-w-6xl px-4 py-12 sm:px-5 sm:py-16">
        <p className="text-xs font-black uppercase tracking-[0.22em] text-[#ed633f] sm:text-sm">
          Pricing
        </p>
        <h1 className="mt-3 max-w-4xl text-4xl font-black tracking-[-0.045em] text-[#101827] sm:text-6xl">
          Automation pricing that makes sense for growing local businesses.
        </h1>
        <p className="mt-5 max-w-3xl text-base leading-7 text-[#59605a] sm:text-lg sm:leading-8">
          Launch pricing keeps BeoOS accessible while you validate the workflows that save time,
          reduce missed deals, and help your business respond faster.
        </p>
        <div className="mt-10 grid gap-4 lg:grid-cols-3">
          {pricing.map((plan) => (
            <article
              key={plan.name}
              className={`rounded-3xl border p-5 sm:p-6 ${
                plan.highlighted ? "border-[#ed633f] bg-[#fff7f3]" : "bg-white"
              }`}
            >
              {plan.highlighted && (
                <p className="mb-3 inline-flex rounded-full bg-[#ed633f] px-3 py-1 text-xs font-black text-white">
                  Recommended
                </p>
              )}
              <h2 className="text-xl font-black sm:text-2xl">{plan.name}</h2>
              <p className="mt-2 text-sm leading-6 text-[#59605a]">{plan.audience}</p>
              <p className="mt-5 text-3xl font-black tracking-[-0.04em] sm:text-4xl">
                {plan.price}
                <span className="text-base font-bold text-[#6f746f]">/month</span>
              </p>
              <ul className="mt-6 grid gap-3 text-sm text-[#59605a]">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex gap-2">
                    <span className="mt-1 size-2 rounded-full bg-[#ed633f]" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
        <Link
          href="/sign-up"
          className="mt-10 inline-flex rounded-full bg-[#ed633f] px-6 py-3 font-black text-white"
        >
          Start with BeoOS
        </Link>
      </section>
    </PublicPageShell>
  );
}

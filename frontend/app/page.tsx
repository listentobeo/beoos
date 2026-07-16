import Link from "next/link";
import { BeoOSFloatingHero } from "@/components/public/beoos-floating-hero";
import { PublicPageShell } from "@/components/public/site-shell";

const features = [
  {
    title: "Unified inbox",
    text: "Bring Zoho Mail, Gmail, WhatsApp, and website form conversations into one business workspace.",
  },
  {
    title: "AI lead qualification",
    text: "Detect serious enquiries, draft contextual acknowledgements, and route real opportunities for approval.",
  },
  {
    title: "Quotations and pricing",
    text: "Turn messages into structured leads, quotes, and pricing decisions without losing business context.",
  },
  {
    title: "Tenant-based operations",
    text: "Each business keeps separate inboxes, contacts, policies, pricing, channels, and automation rules.",
  },
];

const useCases = [
  "Art studios and creative service businesses",
  "Interior, mural, signage, and design teams",
  "Local service providers managing many customer channels",
  "Small teams that need sales follow-up without a full CRM department",
];

const pricing = [
  {
    name: "Starter",
    price: "₦5,000",
    audience: "Solo operators and very small businesses",
    features: [
      "1 business workspace",
      "Unified inbox basics",
      "Website form intake",
      "AI drafts with approval",
      "Basic CRM leads",
    ],
  },
  {
    name: "Growth",
    price: "₦15,000",
    audience: "Growing businesses with active customer conversations",
    highlighted: true,
    features: [
      "Up to 3 business workspaces",
      "Zoho/Gmail + WhatsApp workflows",
      "CRM pipeline and follow-ups",
      "Quotation and pricing catalogue",
      "Push and email alerts",
    ],
  },
  {
    name: "Scale",
    price: "₦30,000",
    audience: "Larger teams managing multiple brands or branches",
    features: [
      "Up to 10 business workspaces",
      "Higher automation usage",
      "Multi-channel approval queues",
      "Advanced pricing/inventory workflows",
      "Priority setup support",
    ],
  },
];

export default function Home() {
  return (
    <PublicPageShell>
      <BeoOSFloatingHero />

      <section id="features" className="border-y bg-white">
        <div className="mx-auto max-w-6xl px-5 py-16">
          <p className="text-sm font-black uppercase tracking-[0.25em] text-[#ed633f]">
            Features
          </p>
          <h2 className="mt-3 max-w-3xl text-4xl font-black tracking-[-0.035em]">
            Everything a business needs before the customer slips through the cracks.
          </h2>
          <div className="mt-10 grid gap-4 md:grid-cols-2">
            {features.map((feature) => (
              <article key={feature.title} className="rounded-3xl border bg-[#f8f7f3] p-6">
                <h3 className="text-xl font-black">{feature.title}</h3>
                <p className="mt-3 leading-7 text-[#59605a]">{feature.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="pricing" className="border-y bg-white">
        <div className="mx-auto max-w-6xl px-5 py-16">
          <p className="text-sm font-black uppercase tracking-[0.25em] text-[#ed633f]">
            Pricing
          </p>
          <h2 className="mt-3 max-w-3xl text-4xl font-black tracking-[-0.035em]">
            Nigerian starter pricing for businesses that need automation without heavy software bills.
          </h2>
          <p className="mt-4 max-w-3xl leading-7 text-[#59605a]">
            These launch plans are designed to validate usage locally. As BeoOS grows, pricing can
            become usage-based for AI messages, connected channels, WhatsApp conversations, storage,
            and team seats.
          </p>
          <div className="mt-10 grid gap-4 lg:grid-cols-3">
            {pricing.map((plan) => (
              <article
                key={plan.name}
                className={`rounded-3xl border p-6 ${
                  plan.highlighted ? "border-[#ed633f] bg-[#fff7f3] shadow-sm" : "bg-[#f8f7f3]"
                }`}
              >
                {plan.highlighted && (
                  <p className="mb-3 inline-flex rounded-full bg-[#ed633f] px-3 py-1 text-xs font-black text-white">
                    Recommended
                  </p>
                )}
                <h3 className="text-2xl font-black">{plan.name}</h3>
                <p className="mt-2 text-sm leading-6 text-[#59605a]">{plan.audience}</p>
                <p className="mt-5 text-4xl font-black tracking-[-0.04em]">
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
                <Link
                  href="/sign-up"
                  className={`mt-6 inline-flex w-full justify-center rounded-full px-5 py-3 font-black ${
                    plan.highlighted
                      ? "bg-[#ed633f] text-white hover:bg-[#de5635]"
                      : "bg-white text-[#101827] hover:border-[#ed633f]"
                  }`}
                >
                  Start with {plan.name}
                </Link>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="how-it-works" className="mx-auto max-w-6xl px-5 py-16">
        <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <p className="text-sm font-black uppercase tracking-[0.25em] text-[#ed633f]">
              How it works
            </p>
            <h2 className="mt-3 text-4xl font-black tracking-[-0.035em]">
              Connect channels, set policy, let AI prepare the work.
            </h2>
            <p className="mt-4 leading-7 text-[#59605a]">
              Business owners stay in control. BeoOS can draft responses, flag urgent items,
              create CRM leads, and prepare quotes, but policy-sensitive actions remain visible
              for approval.
            </p>
          </div>
          <div className="grid gap-3">
            {["Add your business", "Connect email, WhatsApp, or forms", "Write your AI policy", "Review leads, replies, and quotes"].map(
              (step, index) => (
                <div key={step} className="flex gap-4 rounded-3xl border bg-white p-5">
                  <span className="grid size-10 shrink-0 place-items-center rounded-full bg-[#ed633f] font-black text-white">
                    {index + 1}
                  </span>
                  <div>
                    <p className="font-black">{step}</p>
                    <p className="mt-1 text-sm text-[#6f746f]">
                      Tenant-aware setup keeps each business isolated and configurable.
                    </p>
                  </div>
                </div>
              ),
            )}
          </div>
        </div>
      </section>

      <section className="bg-[#101827] px-5 py-16 text-white">
        <div className="mx-auto max-w-6xl">
          <h2 className="max-w-3xl text-4xl font-black tracking-[-0.035em]">
            Built for real-world service businesses.
          </h2>
          <div className="mt-8 grid gap-3 md:grid-cols-2">
            {useCases.map((useCase) => (
              <div key={useCase} className="rounded-2xl bg-white/8 p-4 font-bold">
                {useCase}
              </div>
            ))}
          </div>
        </div>
      </section>
    </PublicPageShell>
  );
}

import Link from "next/link";
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

export default function Home() {
  return (
    <PublicPageShell>
      <section className="mx-auto grid max-w-6xl gap-10 px-5 py-16 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:py-24">
        <div>
          <p className="inline-flex rounded-full border bg-white px-4 py-2 text-sm font-bold text-[#ed633f]">
            AI-powered business communication OS
          </p>
          <h1 className="mt-6 max-w-3xl text-5xl font-black tracking-[-0.045em] text-[#101827] md:text-7xl">
            Run sales, messages, leads, and quotes from one calm dashboard.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-[#59605a]">
            BeoOS helps service businesses capture customer requests, classify leads, prepare
            replies, manage quotations, and keep every channel organized across email, forms,
            WhatsApp, and CRM workflows.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/sign-up"
              className="rounded-full bg-[#ed633f] px-6 py-3 text-center font-black text-white shadow-sm hover:bg-[#de5635]"
            >
              Create BeoOS account
            </Link>
            <Link
              href="/sign-in"
              className="rounded-full border bg-white px-6 py-3 text-center font-black text-[#101827] hover:border-[#ed633f]"
            >
              Sign in
            </Link>
          </div>
          <p className="mt-4 text-sm text-[#6f746f]">
            Built for secure, tenant-based automation. No hardcoded business data.
          </p>
        </div>

        <div className="rounded-[2rem] border bg-white p-4 shadow-sm">
          <div className="rounded-[1.5rem] bg-[#101827] p-5 text-white">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.25em] text-white/50">Today</p>
                <h2 className="mt-2 text-2xl font-black">Business command center</h2>
              </div>
              <span className="rounded-full bg-[#ed633f] px-3 py-1 text-sm font-bold">
                Live
              </span>
            </div>
            <div className="mt-6 grid gap-3">
              {[
                ["New lead", "WhatsApp request captured and scored"],
                ["Quote draft", "Pricing pulled from catalogue"],
                ["Needs approval", "AI reply awaiting owner decision"],
                ["Follow-up", "Customer deadline detected"],
              ].map(([label, text]) => (
                <div key={label} className="rounded-2xl bg-white/8 p-4">
                  <p className="font-bold">{label}</p>
                  <p className="mt-1 text-sm text-white/65">{text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

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

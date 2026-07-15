import Link from "next/link";
import { PublicPageShell } from "@/components/public/site-shell";

export const metadata = { title: "About BeoOS" };

export default function AboutPage() {
  return (
    <PublicPageShell>
      <section className="mx-auto max-w-5xl px-5 py-16">
        <p className="text-sm font-black uppercase tracking-[0.25em] text-[#ed633f]">
          About BeoOS
        </p>
        <h1 className="mt-3 max-w-4xl text-5xl font-black tracking-[-0.045em] text-[#101827] md:text-6xl">
          Built by a founder who needed one operating system for many moving businesses.
        </h1>
        <div className="mt-8 grid gap-8 lg:grid-cols-[0.95fr_1.05fr]">
          <div className="overflow-hidden rounded-[2rem] bg-[#101827] text-white">
            <img
              src="/images/founder-benjamin-odeke.png"
              alt="Benjamin Odeke, founder of BeoOS"
              className="aspect-[4/3] w-full object-cover object-top"
            />
            <div className="p-6">
              <p className="text-sm uppercase tracking-[0.22em] text-white/50">Founder</p>
              <h2 className="mt-3 text-3xl font-black">Benjamin Odeke</h2>
              <p className="mt-4 leading-7 text-white/70">
                BeoOS started from the pressure of running and building multiple businesses at the
                same time. Messages were spread across email, WhatsApp, website forms, CRM notes,
                quotes, pricing sheets, and follow-up reminders.
              </p>
              <p className="mt-4 leading-7 text-white/70">
                The bigger software stacks could solve parts of the problem, but paying separate
                fees for every tool was heavy for a growing Nigerian business. BeoOS was built to
                bring the important pieces into one practical system.
              </p>
            </div>
          </div>
          <div className="grid gap-4">
            {[
              [
                "Why it exists",
                "To help service businesses capture leads, understand requests, prepare replies, quote faster, follow up on time, and stay aware of what needs approval.",
              ],
              [
                "Who it is for",
                "Studios, agencies, local service teams, consultants, schools, clinics, repair businesses, and any team that sells through conversations.",
              ],
              [
                "How it works",
                "Each business gets its own tenant workspace with separate inboxes, contacts, policies, pricing, quotes, alerts, and connected channels.",
              ],
            ].map(([title, body]) => (
              <article key={title} className="rounded-3xl border bg-white p-6">
                <h2 className="text-xl font-black">{title}</h2>
                <p className="mt-3 leading-7 text-[#59605a]">{body}</p>
              </article>
            ))}
          </div>
        </div>

        <div className="mt-10 rounded-3xl border bg-white p-6">
          <h2 className="text-2xl font-black">The BeoOS direction</h2>
          <p className="mt-3 max-w-3xl leading-7 text-[#59605a]">
            BeoOS is becoming a command center for business communication: one place for customer
            messages, AI-assisted replies, CRM leads, quotations, pricing/inventory, follow-up
            scheduling, and approval alerts. The goal is simple: fewer missed deals, less tool
            switching, and more control for business owners.
          </p>
          <div className="mt-6 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/sign-up"
              className="rounded-full bg-[#ed633f] px-6 py-3 text-center font-black text-white shadow-sm hover:bg-[#de5635]"
            >
              Create account
            </Link>
            <Link
              href="/support"
              className="rounded-full border bg-white px-6 py-3 text-center font-black text-[#101827] hover:border-[#ed633f]"
            >
              Contact support
            </Link>
          </div>
        </div>
      </section>
    </PublicPageShell>
  );
}

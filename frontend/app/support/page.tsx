import Link from "next/link";
import { PublicPageShell } from "@/components/public/site-shell";

export default function SupportPage() {
  return (
    <PublicPageShell>
      <section className="mx-auto max-w-4xl px-5 py-16">
        <p className="text-sm font-black uppercase tracking-[0.25em] text-[#ed633f]">
          Support
        </p>
        <h1 className="mt-3 text-5xl font-black tracking-[-0.045em] text-[#101827]">
          Contact BeoOS support
        </h1>
        <p className="mt-5 max-w-2xl text-lg leading-8 text-[#59605a]">
          Need help with onboarding, channel connections, WhatsApp setup, email sync, AI policy,
          pricing, or quotations? Contact the BeoOS team and include your business name.
        </p>

        <div className="mt-10 grid gap-5 md:grid-cols-2">
          <div className="rounded-3xl border bg-white p-6">
            <h2 className="text-xl font-black">Email</h2>
            <p className="mt-3 text-[#59605a]">
              For support requests, account questions, or data deletion help.
            </p>
            <a
              href="mailto:support@beoos.com.ng"
              className="mt-5 inline-flex rounded-full bg-[#ed633f] px-5 py-3 font-black text-white"
            >
              support@beoos.com.ng
            </a>
          </div>
          <div className="rounded-3xl border bg-white p-6">
            <h2 className="text-xl font-black">Useful links</h2>
            <div className="mt-4 grid gap-3 text-sm font-semibold text-[#59605a]">
              <Link href="/privacy">Privacy Policy</Link>
              <Link href="/terms">Terms of Service</Link>
              <Link href="/data-deletion">Data Deletion Instructions</Link>
              <Link href="/sign-in">Sign in to BeoOS</Link>
            </div>
          </div>
        </div>
      </section>
    </PublicPageShell>
  );
}

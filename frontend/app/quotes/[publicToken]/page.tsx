import { Banknote, CheckCircle2, FileText, ListChecks } from "lucide-react";
import { AcceptQuoteButton } from "@/components/public/accept-quote-button";
import { PrintProposalButton } from "@/components/public/print-proposal-button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type PublicQuote = {
  title: string;
  business_name: string;
  contact_name: string | null;
  contact_email: string | null;
  status: string;
  currency: string;
  total: string;
  deposit_required: string | null;
  proposal: Record<string, unknown>;
  calculation: Record<string, unknown>;
  payment_url: string | null;
  accepted_at: string | null;
};

export const metadata = {
  title: "Proposal",
  robots: { index: false, follow: false },
};

function text(value: unknown, fallback = "Not set") {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function money(value: string | null | undefined, currency = "NGN") {
  const amount = Number(value ?? 0);
  if (!amount) return "Not calculated";
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
}

function design(quote: PublicQuote) {
  const raw = quote.proposal.design;
  const settings = raw && typeof raw === "object" ? raw as Record<string, unknown> : {};
  const accent = typeof settings.accent_color === "string" ? settings.accent_color : "#ed633f";
  return { accent };
}

function lineItems(quote: PublicQuote) {
  const raw = quote.calculation.line_items;
  return Array.isArray(raw) ? raw.filter((item) => item && typeof item === "object") as Array<Record<string, unknown>> : [];
}

async function getQuote(publicToken: string) {
  const response = await fetch(`${API_URL}/quotes/${publicToken}`, { cache: "no-store" });
  if (!response.ok) return null;
  return response.json() as Promise<PublicQuote>;
}

export default async function PublicQuotePage({
  params,
}: {
  params: Promise<{ publicToken: string }>;
}) {
  const { publicToken } = await params;
  const quote = await getQuote(publicToken);

  if (!quote) {
    return (
      <main className="grid min-h-screen place-items-center bg-[#f5f1ea] px-4 py-10">
        <Card className="max-w-md p-8 text-center">
          <FileText className="mx-auto size-8 text-[#ed633f]" />
          <h1 className="mt-4 text-xl font-bold">Proposal not found</h1>
          <p className="mt-2 text-sm leading-6 text-[#747973]">
            This proposal link may be incorrect or no longer available.
          </p>
        </Card>
      </main>
    );
  }

  const theme = design(quote);
  const items = lineItems(quote);

  return (
    <main className="min-h-screen bg-[#f5f1ea] px-4 py-8 print:bg-white print:px-0 print:py-0 sm:px-6">
      <div className="mx-auto max-w-5xl">
        <div className="mb-4 flex justify-end print:hidden">
          <PrintProposalButton />
        </div>
        <header className="rounded-3xl bg-[#101827] p-6 text-white print:rounded-none sm:p-8" style={{ borderTop: `6px solid ${theme.accent}` }}>
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-white/45">
            {quote.business_name}
          </p>
          <h1 className="mt-3 text-3xl font-black tracking-[-0.04em] sm:text-5xl">
            {quote.title}
          </h1>
          <p className="mt-3 text-sm text-white/65">
            Prepared for {quote.contact_name || quote.contact_email || "client"}
          </p>
        </header>

        <section className="mt-5 grid gap-4 md:grid-cols-3">
          <Card className="p-5">
            <p className="text-xs font-bold uppercase tracking-wider text-[#90948f]">Total</p>
            <p className="mt-2 text-3xl font-black">{money(quote.total, quote.currency)}</p>
          </Card>
          <Card className="p-5">
            <p className="text-xs font-bold uppercase tracking-wider text-[#90948f]">Deposit</p>
            <p className="mt-2 text-3xl font-black">
              {money(quote.deposit_required, quote.currency)}
            </p>
          </Card>
          <Card className="p-5">
            <p className="text-xs font-bold uppercase tracking-wider text-[#90948f]">Status</p>
            <div className="mt-3">
              <Badge className="bg-emerald-50 text-emerald-700">
                {quote.status.replaceAll("_", " ")}
              </Badge>
            </div>
          </Card>
        </section>

        <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_340px]">
          <section className="space-y-5">
            <Card className="p-6">
              <h2 className="flex items-center gap-2 font-bold">
                <FileText className="size-4 text-[#ed633f]" />
                Proposal
              </h2>
              <dl className="mt-5 space-y-4 text-sm leading-7">
                <div><dt className="font-bold">Summary</dt><dd className="mt-1 text-[#626862]">{text(quote.proposal.summary)}</dd></div>
                <div><dt className="font-bold">Scope</dt><dd className="mt-1 text-[#626862]">{text(quote.proposal.scope)}</dd></div>
                <div><dt className="font-bold">Objectives</dt><dd className="mt-1 text-[#626862]">{text(quote.proposal.objectives)}</dd></div>
                <div><dt className="font-bold">Timeline</dt><dd className="mt-1 text-[#626862]">{text(quote.proposal.timeline)}</dd></div>
                <div><dt className="font-bold">Payment terms</dt><dd className="mt-1 text-[#626862]">{text(quote.proposal.payment_terms)}</dd></div>
                <div><dt className="font-bold">Exclusions</dt><dd className="mt-1 text-[#626862]">{text(quote.proposal.exclusions)}</dd></div>
                <div><dt className="font-bold">Warranty</dt><dd className="mt-1 text-[#626862]">{text(quote.proposal.warranty)}</dd></div>
              </dl>
            </Card>

            {items.length > 0 && (
              <Card className="overflow-hidden">
                <div className="border-b px-6 py-5">
                  <h2 className="flex items-center gap-2 font-bold">
                    <ListChecks className="size-4" style={{ color: theme.accent }} />
                    Itemized quote
                  </h2>
                  <p className="mt-1 text-sm text-[#747973]">
                    Products, services, quantities, and calculated totals.
                  </p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[680px] text-sm">
                    <thead className="bg-[#fbfaf7] text-left text-[11px] uppercase tracking-wider text-[#858a84]">
                      <tr>
                        <th className="px-6 py-3">Item</th>
                        <th className="px-6 py-3">Qty</th>
                        <th className="px-6 py-3">Unit price</th>
                        <th className="px-6 py-3 text-right">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {items.map((item, index) => (
                        <tr key={`${String(item.label)}-${index}`}>
                          <td className="px-6 py-4">
                            <p className="font-bold">{text(item.label)}</p>
                            <p className="mt-1 text-xs text-[#747973]">{text(item.description, "")}</p>
                          </td>
                          <td className="px-6 py-4">{text(item.quantity, "1")}</td>
                          <td className="px-6 py-4">{money(String(item.unit_price ?? 0), quote.currency)}</td>
                          <td className="px-6 py-4 text-right font-bold">
                            {money(String(item.total ?? 0), quote.currency)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
          </section>

          <aside className="space-y-5">
            <Card className="p-6">
              <h2 className="flex items-center gap-2 font-bold">
                <CheckCircle2 className="size-4 text-[#ed633f]" />
                Accept proposal
              </h2>
              <p className="mt-3 text-sm leading-6 text-[#747973]">
                Accepting confirms you want to proceed with this proposal. If a deposit link has been prepared, you can pay immediately after accepting.
              </p>
              <div className="mt-5">
                <AcceptQuoteButton
                  publicToken={publicToken}
                  accepted={Boolean(quote.accepted_at)}
                  paymentUrl={quote.payment_url}
                />
              </div>
            </Card>

            <Card className="p-6">
              <h2 className="flex items-center gap-2 font-bold">
                <Banknote className="size-4 text-[#ed633f]" />
                Payment
              </h2>
              <p className="mt-3 text-sm leading-6 text-[#747973]">
                Deposit required: {money(quote.deposit_required, quote.currency)}.
              </p>
            </Card>
          </aside>
        </div>
      </div>
    </main>
  );
}

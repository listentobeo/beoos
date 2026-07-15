import { ArrowLeft, Banknote, ClipboardList, FileText } from "lucide-react";
import Link from "next/link";
import { DeleteQuoteButton } from "@/components/dashboard/delete-quote-button";
import { QuotePaymentButton } from "@/components/dashboard/quote-actions";
import { QuoteEditForm } from "@/components/dashboard/quote-edit-form";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { activeBusiness, beoApi, type Quote } from "@/lib/api";

export const metadata = { title: "Quote detail" };

const statusStyles: Record<string, string> = {
  draft: "bg-slate-100 text-slate-700",
  needs_approval: "bg-amber-50 text-amber-700",
  approved: "bg-blue-50 text-blue-700",
  sent: "bg-violet-50 text-violet-700",
  accepted: "bg-emerald-50 text-emerald-700",
  rejected: "bg-red-50 text-red-700",
  expired: "bg-zinc-100 text-zinc-500",
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

function calculationRows(quote: Quote): [string, unknown][] {
  const calculation = quote.calculation;
  const rows: [string, unknown][] = [
    ["Design", calculation.design],
    ["Labor", calculation.labor],
    ["Materials", calculation.materials],
    ["Equipment", calculation.equipment],
    ["Transport", calculation.transport],
    ["Project management", calculation.project_management],
    ["Overhead", calculation.overhead],
    ["Risk allowance", calculation.risk],
    ["Profit", calculation.profit],
  ];
  return rows.filter(([, value]) => value !== undefined && value !== null);
}

function lineItems(quote: Quote) {
  const items = quote.calculation.line_items;
  return Array.isArray(items) ? items.filter((item) => typeof item === "object" && item) : [];
}

function accentColor(quote: Quote) {
  const design = quote.proposal.design;
  if (design && typeof design === "object" && "accent_color" in design) {
    const accent = (design as Record<string, unknown>).accent_color;
    if (typeof accent === "string" && accent.trim()) return accent;
  }
  return "#ed633f";
}

export default async function QuoteDetailPage({
  params,
}: {
  params: Promise<{ quoteId: string }>;
}) {
  let quote: Quote | null = null;
  let businessId: string | null = null;
  const { quoteId } = await params;

  try {
    const business = await activeBusiness();
    if (business) {
      businessId = business.id;
      quote = await beoApi.quote(business.id, quoteId);
    }
  } catch {
    quote = null;
  }

  if (!quote) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8 md:px-8">
        <Link href="/dashboard/quotes" className="inline-flex items-center gap-2 text-sm text-[#747973] hover:text-[#171b23]">
          <ArrowLeft className="size-4" /> Back to quotations
        </Link>
        <Card className="mt-6 p-8 text-center">
          <FileText className="mx-auto size-8 text-[#ed633f]" />
          <h1 className="mt-3 text-lg font-bold">Quote could not be loaded</h1>
          <p className="mt-1 text-sm text-[#747973]">Refresh the quotations page or confirm the backend deployment is current.</p>
        </Card>
      </div>
    );
  }

  const proposal = quote.proposal;
  const input = quote.input_data;
  const rows = calculationRows(quote);
  const quoteLineItems = lineItems(quote) as Array<Record<string, unknown>>;
  const isMuralQuote = quote.template_type === "mural";
  const accent = accentColor(quote);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 md:px-8">
      <Link href="/dashboard/quotes" className="inline-flex items-center gap-2 text-sm text-[#747973] hover:text-[#171b23]">
        <ArrowLeft className="size-4" /> Back to quotations
      </Link>

      <header className="mt-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge className={statusStyles[quote.status] ?? statusStyles.draft}>
            {quote.status.replaceAll("_", " ")}
          </Badge>
          <Badge className="bg-orange-50 text-[#c94d2d]">
            {quote.template_type.replaceAll("_", " ")} template
          </Badge>
          {quote.template_id && <Badge className="bg-blue-50 text-blue-700">tenant template</Badge>}
        </div>
        <h1 className="mt-3 text-2xl font-bold tracking-[-0.035em] text-[#171b23] sm:text-3xl">{quote.title}</h1>
        <p className="mt-1 text-sm text-[#747973]">
          {quote.contact_name || quote.contact_email || "No client attached"} · Updated {new Date(quote.updated_at).toLocaleString()}
        </p>
      </header>

      <section className="mt-7 grid gap-4 md:grid-cols-3">
        <Card className="p-5">
          <p className="text-xs font-bold uppercase tracking-wider text-[#90948f]">Total</p>
          <p className="mt-2 text-3xl font-black tracking-tight">{money(quote.total, quote.currency)}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs font-bold uppercase tracking-wider text-[#90948f]">Deposit required</p>
          <p className="mt-2 text-3xl font-black tracking-tight">
            {money(quote.deposit_required, quote.currency)}
          </p>
        </Card>
        <Card className="p-5">
          <p className="text-xs font-bold uppercase tracking-wider text-[#90948f]">
            {isMuralQuote ? "Area" : "Line items"}
          </p>
          {isMuralQuote ? (
            <p className="mt-2 text-lg font-bold">
              {text((quote.calculation.area as { sqft?: string } | undefined)?.sqft)} sqft
            </p>
          ) : (
            <p className="mt-2 text-3xl font-black tracking-tight">{quoteLineItems.length}</p>
          )}
        </Card>
      </section>

      <div className="mt-7 grid gap-5 lg:grid-cols-[1fr_380px]">
        <section className="space-y-5">
          <Card className="p-5">
            <div className="flex items-center gap-2">
              <ClipboardList className="size-4 text-[#ed633f]" />
              <h2 className="font-bold">Client proposal</h2>
            </div>
            <dl className="mt-5 space-y-4 text-sm leading-6">
              <div><dt className="font-bold">Summary</dt><dd className="mt-1 text-[#666b65]">{text(proposal.summary)}</dd></div>
              {isMuralQuote && <div><dt className="font-bold">Problem</dt><dd className="mt-1 text-[#666b65]">{text(proposal.problem)}</dd></div>}
              {isMuralQuote && <div><dt className="font-bold">Objectives</dt><dd className="mt-1 text-[#666b65]">{text(proposal.objectives)}</dd></div>}
              <div><dt className="font-bold">Scope</dt><dd className="mt-1 text-[#666b65]">{text(proposal.scope)}</dd></div>
              <div><dt className="font-bold">Timeline</dt><dd className="mt-1 text-[#666b65]">{text(proposal.timeline)}</dd></div>
              <div><dt className="font-bold">Payment terms</dt><dd className="mt-1 text-[#666b65]">{text(proposal.payment_terms)}</dd></div>
              <div><dt className="font-bold">Assumptions</dt><dd className="mt-1 text-[#666b65]">{text(proposal.assumptions)}</dd></div>
              <div><dt className="font-bold">Exclusions</dt><dd className="mt-1 text-[#666b65]">{text(proposal.exclusions)}</dd></div>
              <div><dt className="font-bold">Warranty</dt><dd className="mt-1 text-[#666b65]">{text(proposal.warranty)}</dd></div>
            </dl>
          </Card>

          {quoteLineItems.length > 0 && (
            <Card className="overflow-hidden">
              <div className="border-b px-5 py-4" style={{ borderColor: `${accent}33` }}>
                <h2 className="font-bold">Line items</h2>
                <p className="mt-1 text-sm text-[#747973]">
                  Flexible itemized pricing for products, bulk purchases, and service packages.
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-sm">
                  <thead className="bg-[#fbfaf7] text-left text-[11px] uppercase tracking-wider text-[#858a84]">
                    <tr>
                      <th className="px-5 py-3">Item</th>
                      <th className="px-5 py-3">Qty</th>
                      <th className="px-5 py-3">Unit price</th>
                      <th className="px-5 py-3">Discount</th>
                      <th className="px-5 py-3">Tax</th>
                      <th className="px-5 py-3 text-right">Total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {quoteLineItems.map((item, index) => (
                      <tr key={`${String(item.label)}-${index}`}>
                        <td className="px-5 py-4">
                          <p className="font-bold">{text(item.label)}</p>
                          <p className="mt-1 text-xs text-[#747973]">{text(item.description, "")}</p>
                        </td>
                        <td className="px-5 py-4">{text(item.quantity, "1")}</td>
                        <td className="px-5 py-4">{money(String(item.unit_price ?? 0), quote.currency)}</td>
                        <td className="px-5 py-4">{text(item.discount_percent, "0")}%</td>
                        <td className="px-5 py-4">{text(item.tax_percent, "0")}%</td>
                        <td className="px-5 py-4 text-right font-bold">
                          {money(String(item.total ?? 0), quote.currency)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {rows.length > 0 && (
            <Card className="p-5">
              <div className="flex items-center gap-2">
                <Banknote className="size-4 text-[#ed633f]" />
                <h2 className="font-bold">Cost breakdown</h2>
              </div>
              <div className="mt-4 divide-y rounded-xl border">
                {rows.map(([label, value]) => (
                  <div key={label} className="flex items-center justify-between gap-4 px-4 py-3 text-sm">
                    <span className="text-[#666b65]">{label}</span>
                    <span className="font-bold tabular-nums">{money(String(value), quote.currency)}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </section>

        <aside className="space-y-5">
          <Card className="p-5">
            <h2 className="font-bold">Client link</h2>
            <p className="mt-2 break-all rounded-xl bg-[#f7f6f2] p-3 text-xs leading-5 text-[#545a54]">
              {quote.public_url || "Public link will appear after backend migration."}
            </p>
            {quote.payment_url && (
              <a
                href={quote.payment_url}
                target="_blank"
                rel="noreferrer"
                className="mt-3 block break-all text-xs font-semibold text-[#ed633f]"
              >
                Open Paystack deposit link
              </a>
            )}
            {businessId && (
              <div className="mt-4">
                <QuotePaymentButton
                  businessId={businessId}
                  quoteId={quote.id}
                  hasPaymentUrl={Boolean(quote.payment_url)}
                />
              </div>
            )}
          </Card>

          {isMuralQuote ? (
            <Card className="p-5">
              <h2 className="font-bold">Mural project input</h2>
              <dl className="mt-4 space-y-3 text-sm">
                <div><dt className="text-[#747973]">Project type</dt><dd className="font-semibold">{text(input.project_type)}</dd></div>
                <div><dt className="text-[#747973]">Location</dt><dd className="font-semibold">{text(input.project_location)}</dd></div>
                <div><dt className="text-[#747973]">Deadline</dt><dd className="font-semibold">{text(input.deadline)}</dd></div>
                <div><dt className="text-[#747973]">Surface</dt><dd className="font-semibold">{text(input.surface_type)} · {text(input.surface_condition)}</dd></div>
                <div><dt className="text-[#747973]">Access</dt><dd className="font-semibold">{text(input.access)}</dd></div>
                <div><dt className="text-[#747973]">Environment</dt><dd className="font-semibold">{text(input.environment)}</dd></div>
              </dl>
            </Card>
          ) : (
            <Card className="p-5">
              <h2 className="font-bold">Template design</h2>
              <div className="mt-4 rounded-2xl p-4 text-white" style={{ backgroundColor: accent }}>
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-white/65">Accent color</p>
                <p className="mt-2 text-lg font-black">{accent}</p>
              </div>
              <p className="mt-3 text-sm leading-6 text-[#747973]">
                This color is used on the client-facing proposal header and print/PDF view.
              </p>
            </Card>
          )}

          {businessId && isMuralQuote && (
            <Card className="p-5">
              <h2 className="font-bold">Edit mural quote basics</h2>
              <p className="mt-2 text-sm leading-6 text-[#747973]">
                Update the key mural inputs before sharing the proposal link.
              </p>
              <div className="mt-4">
                <QuoteEditForm businessId={businessId} quote={quote} />
              </div>
            </Card>
          )}

          <Card className="p-5">
            <h2 className="font-bold">Approval path</h2>
            <p className="mt-2 text-sm leading-6 text-[#747973]">
              Quotes start as drafts. Share the client link when the value, terms, and design look right.
            </p>
          </Card>

          {businessId && (
            <Card className="border-red-100 p-5">
              <h2 className="font-bold text-red-700">Danger zone</h2>
              <p className="mt-2 text-sm leading-6 text-[#747973]">
                Remove test or duplicate quotes. This does not delete the CRM lead or inbox thread.
              </p>
              <div className="mt-4">
                <DeleteQuoteButton businessId={businessId} quoteId={quote.id} />
              </div>
            </Card>
          )}
        </aside>
      </div>
    </div>
  );
}

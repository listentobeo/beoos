import { ArrowLeft, Banknote, ClipboardList, FileText } from "lucide-react";
import Link from "next/link";
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
          <p className="text-xs font-bold uppercase tracking-wider text-[#90948f]">Area</p>
          <p className="mt-2 text-lg font-bold">
            {text((quote.calculation.area as { sqft?: string } | undefined)?.sqft)} sqft
          </p>
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
              <div><dt className="font-bold">Problem</dt><dd className="mt-1 text-[#666b65]">{text(proposal.problem)}</dd></div>
              <div><dt className="font-bold">Objectives</dt><dd className="mt-1 text-[#666b65]">{text(proposal.objectives)}</dd></div>
              <div><dt className="font-bold">Scope</dt><dd className="mt-1 text-[#666b65]">{text(proposal.scope)}</dd></div>
              <div><dt className="font-bold">Timeline</dt><dd className="mt-1 text-[#666b65]">{text(proposal.timeline)}</dd></div>
              <div><dt className="font-bold">Payment terms</dt><dd className="mt-1 text-[#666b65]">{text(proposal.payment_terms)}</dd></div>
              <div><dt className="font-bold">Assumptions</dt><dd className="mt-1 text-[#666b65]">{text(proposal.assumptions)}</dd></div>
              <div><dt className="font-bold">Exclusions</dt><dd className="mt-1 text-[#666b65]">{text(proposal.exclusions)}</dd></div>
              <div><dt className="font-bold">Warranty</dt><dd className="mt-1 text-[#666b65]">{text(proposal.warranty)}</dd></div>
            </dl>
          </Card>

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

          <Card className="p-5">
            <h2 className="font-bold">Project input</h2>
            <dl className="mt-4 space-y-3 text-sm">
              <div><dt className="text-[#747973]">Project type</dt><dd className="font-semibold">{text(input.project_type)}</dd></div>
              <div><dt className="text-[#747973]">Location</dt><dd className="font-semibold">{text(input.project_location)}</dd></div>
              <div><dt className="text-[#747973]">Deadline</dt><dd className="font-semibold">{text(input.deadline)}</dd></div>
              <div><dt className="text-[#747973]">Surface</dt><dd className="font-semibold">{text(input.surface_type)} · {text(input.surface_condition)}</dd></div>
              <div><dt className="text-[#747973]">Access</dt><dd className="font-semibold">{text(input.access)}</dd></div>
              <div><dt className="text-[#747973]">Environment</dt><dd className="font-semibold">{text(input.environment)}</dd></div>
            </dl>
          </Card>

          {businessId && (
            <Card className="p-5">
              <h2 className="font-bold">Edit quote basics</h2>
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
              Quotes start as drafts. Later we can add owner approval, PDF export, client acceptance links, and deposit tracking on top of this base engine.
            </p>
          </Card>
        </aside>
      </div>
    </div>
  );
}

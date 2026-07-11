import { CircleDollarSign, FileText, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { activeBusiness, beoApi, type Quote } from "@/lib/api";

export const metadata = { title: "Quotations" };

const statusStyles: Record<string, string> = {
  draft: "bg-slate-100 text-slate-700",
  needs_approval: "bg-amber-50 text-amber-700",
  approved: "bg-blue-50 text-blue-700",
  sent: "bg-violet-50 text-violet-700",
  accepted: "bg-emerald-50 text-emerald-700",
  rejected: "bg-red-50 text-red-700",
  expired: "bg-zinc-100 text-zinc-500",
};

function money(value: string | null | undefined, currency = "NGN") {
  const amount = Number(value ?? 0);
  if (!amount) return "Not calculated";
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
}

function quoteStats(quotes: Quote[]) {
  const open = quotes.filter((quote) => !["accepted", "rejected", "expired"].includes(quote.status));
  const accepted = quotes.filter((quote) => quote.status === "accepted");
  return {
    total: quotes.length,
    open: open.length,
    accepted: accepted.length,
    openValue: open.reduce((sum, quote) => sum + Number(quote.total ?? 0), 0),
  };
}

export default async function QuotesPage() {
  let quotes: Quote[] = [];
  let businessName = "Current business";

  try {
    const business = await activeBusiness();
    if (business) {
      businessName = business.name;
      quotes = await beoApi.quotes(business.id);
    }
  } catch {}

  const stats = quoteStats(quotes);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-5 md:px-8">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#90948f]">{businessName}</p>
      <h1 className="mt-1 text-3xl font-bold tracking-[-0.035em]">Quotations</h1>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-[#747973]">
        Generic quotation engine for service businesses. Today it includes the mural template, but the same system can support any brick-and-mortar service template.
      </p>

      <section className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Card className="flex items-center gap-4 p-4">
          <div className="grid size-10 place-items-center rounded-xl bg-orange-50 text-[#ed633f]">
            <FileText className="size-4" />
          </div>
          <div><p className="text-2xl font-bold">{stats.total}</p><p className="text-xs text-[#747973]">Total quotes</p></div>
        </Card>
        <Card className="flex items-center gap-4 p-4">
          <div className="grid size-10 place-items-center rounded-xl bg-blue-50 text-blue-700">
            <ShieldCheck className="size-4" />
          </div>
          <div><p className="text-2xl font-bold">{stats.open}</p><p className="text-xs text-[#747973]">Open quotes</p></div>
        </Card>
        <Card className="flex items-center gap-4 p-4">
          <div className="grid size-10 place-items-center rounded-xl bg-emerald-50 text-emerald-700">
            <ShieldCheck className="size-4" />
          </div>
          <div><p className="text-2xl font-bold">{stats.accepted}</p><p className="text-xs text-[#747973]">Accepted</p></div>
        </Card>
        <Card className="flex items-center gap-4 p-4">
          <div className="grid size-10 place-items-center rounded-xl bg-amber-50 text-amber-700">
            <CircleDollarSign className="size-4" />
          </div>
          <div><p className="text-lg font-bold">{money(String(stats.openValue))}</p><p className="text-xs text-[#747973]">Open value</p></div>
        </Card>
      </section>

      <Card className="mt-7 overflow-hidden">
        <div className="grid grid-cols-[1.5fr_1fr_1fr_auto] gap-4 border-b bg-[#fbfaf7] px-5 py-3 text-[11px] font-bold uppercase tracking-wider text-[#858a84]">
          <span>Quote</span><span>Client</span><span>Total</span><span>Status</span>
        </div>
        <div className="divide-y">
          {quotes.map((quote) => (
            <Link
              key={quote.id}
              href={`/dashboard/quotes/${quote.id}`}
              className="grid grid-cols-[1.5fr_1fr_1fr_auto] items-center gap-4 px-5 py-4 text-sm transition hover:bg-[#fffaf7]"
            >
              <div>
                <p className="font-bold text-[#20242b]">{quote.title}</p>
                <p className="mt-1 text-xs text-[#747973]">
                  {quote.template_type.replaceAll("_", " ")} template · {quote.lead_title || "Manual quote"}
                </p>
              </div>
              <span className="truncate text-[#747973]">
                {quote.contact_name || quote.contact_email || "No client attached"}
              </span>
              <span className="font-bold tabular-nums">{money(quote.total, quote.currency)}</span>
              <Badge className={statusStyles[quote.status] ?? statusStyles.draft}>
                {quote.status.replaceAll("_", " ")}
              </Badge>
            </Link>
          ))}
          {quotes.length === 0 && (
            <div className="grid min-h-72 place-items-center p-8 text-center">
              <div>
                <FileText className="mx-auto size-8 text-[#ed633f]" />
                <h2 className="mt-4 font-bold">No quotations yet</h2>
                <p className="mt-2 max-w-md text-sm leading-6 text-[#747973]">
                  Open the CRM pipeline and click “Create quote” on a lead. BeoOS will generate the first mural quotation from the lead and business context.
                </p>
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

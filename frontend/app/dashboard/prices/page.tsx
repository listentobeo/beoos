import { ExternalLink, Tags } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { activeBusiness, beoApi, type PriceItem } from "@/lib/api";

export const metadata = { title: "Price catalogue" };

function money(value: string | null) {
  if (!value) return "Custom quote";
  return new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 }).format(Number(value));
}

export default async function PricesPage() {
  let prices: PriceItem[] = [];
  let businessName = "Current business";
  try {
    const business = await activeBusiness();
    if (business) {
      businessName = business.name;
      prices = await beoApi.prices(business.id);
    }
  } catch {}

  return (
    <div className="mx-auto max-w-6xl px-5 py-8 md:px-8">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#90948f]">{businessName}</p>
      <h1 className="mt-1 text-3xl font-bold tracking-[-0.035em]">Price catalogue</h1>
      <p className="mt-2 text-sm text-[#747973]">Approved service-page prices. Blog estimates are never used as quotations.</p>
      <Card className="mt-7 overflow-hidden">
        <div className="grid grid-cols-[1fr_1fr_auto] gap-4 border-b bg-[#fbfaf7] px-5 py-3 text-[11px] font-bold uppercase tracking-wider text-[#858a84]">
          <span>Service</span><span>Package</span><span>Approved range</span>
        </div>
        <div className="divide-y">
          {prices.map((item) => (
            <div key={item.id} className="grid grid-cols-[1fr_1fr_auto] items-center gap-4 px-5 py-4 text-sm">
              <div><Badge className="bg-[#fff0ea] text-[#c94d2d]">{item.service.replaceAll("_", " ")}</Badge></div>
              <a href={item.source_url} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 font-medium hover:text-[#ed633f]">{item.label}<ExternalLink className="size-3" /></a>
              <span className="font-bold tabular-nums">{money(item.amount_min)}{item.amount_max && item.amount_max !== item.amount_min ? ` – ${money(item.amount_max)}` : ""}{item.amount_min && !item.amount_max ? "+" : ""}</span>
            </div>
          ))}
          {prices.length === 0 && <div className="grid min-h-56 place-items-center text-center"><div><Tags className="mx-auto size-7 text-[#ed633f]"/><p className="mt-3 font-bold">Prices appear after the database seed.</p></div></div>}
        </div>
      </Card>
    </div>
  );
}

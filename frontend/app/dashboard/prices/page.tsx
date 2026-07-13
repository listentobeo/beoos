import { Tags } from "lucide-react";
import { PriceCatalogueManager } from "@/components/dashboard/price-catalogue-manager";
import { Card } from "@/components/ui/card";
import { activeBusiness, beoApi, type PriceItem } from "@/lib/api";

export const metadata = { title: "Price catalogue" };

export default async function PricesPage() {
  let prices: PriceItem[] = [];
  let businessId: string | null = null;
  let businessName = "Current business";
  try {
    const business = await activeBusiness();
    if (business) {
      businessId = business.id;
      businessName = business.name;
      prices = await beoApi.prices(business.id);
    }
  } catch {}

  return (
    <div className="mx-auto max-w-6xl px-5 py-8 md:px-8">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#90948f]">{businessName}</p>
      <h1 className="mt-1 text-3xl font-bold tracking-[-0.035em]">Price catalogue</h1>
      <p className="mt-2 text-sm text-[#747973]">
        Tenant-owned pricing and inventory brain. Use it for portraits, murals, products, quantities,
        and custom fields that quotes and AI can reference.
      </p>

      {businessId ? (
        <PriceCatalogueManager businessId={businessId} prices={prices} />
      ) : (
        <Card className="mt-7 grid min-h-56 place-items-center text-center">
          <div>
            <Tags className="mx-auto size-7 text-[#ed633f]" />
            <p className="mt-3 font-bold">Create a business first.</p>
          </div>
        </Card>
      )}
    </div>
  );
}

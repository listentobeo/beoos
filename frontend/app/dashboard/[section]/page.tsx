import { Construction } from "lucide-react";
import { InboxTable } from "@/components/dashboard/inbox-table";
import { Card } from "@/components/ui/card";
import { activeBusiness, beoApi, type Thread } from "@/lib/api";

export default async function DashboardSectionPage({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  const filters: Record<string, { category?: string; status?: string; provider?: string }> = {
    urgent: { category: "urgent" },
    clients: { category: "existing_client" },
    whatsapp: { provider: "whatsapp" },
  };
  let threads: Thread[] | null = null;
  if (filters[section]) {
    try {
      const business = await activeBusiness();
      threads = business ? await beoApi.threads(business.id, filters[section]) : [];
    } catch {
      threads = [];
    }
  }
  return (
    <div className="mx-auto max-w-5xl px-5 py-8 md:px-8">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#90948f]">
        BeoOS workspace
      </p>
      <h1 className="mt-1 text-3xl font-bold capitalize tracking-[-0.035em]">{section.replaceAll("-", " ")}</h1>
      {threads ? (
        <Card className="mt-7 overflow-hidden"><InboxTable threads={threads} /></Card>
      ) : (
        <Card className="mt-7 grid min-h-72 place-items-center p-8 text-center">
          <div>
            <Construction className="mx-auto size-8 text-[#ed633f]" />
            <p className="mt-4 font-bold">This workspace is ready for the next workflow upgrade.</p>
            <p className="mt-1 text-sm text-[#777c76]">Live data will populate it after the Zoho connection is authorized.</p>
          </div>
        </Card>
      )}
    </div>
  );
}

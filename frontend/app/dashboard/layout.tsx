import { Sidebar } from "@/components/dashboard/sidebar";
import { beoApi } from "@/lib/api";
import { activeBusiness, type Business } from "@/lib/api";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  let businesses: Business[] = [];
  let activeId: string | null = null;
  try {
    businesses = await beoApi.businesses();
    activeId = (await activeBusiness(businesses))?.id ?? null;
  } catch {
    // The page below presents a connection state; the shell should remain usable.
  }
  return (
    <div className="min-h-screen">
      <Sidebar businesses={businesses} activeId={activeId} />
      <main className="min-h-screen lg:pl-[264px]">{children}</main>
    </div>
  );
}

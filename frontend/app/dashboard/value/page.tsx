import { Activity, Gauge } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { activeBusiness, beoApi, type ValueMetric } from "@/lib/api";

export const metadata = { title: "Business value" };

const categoryLabels = {
  revenue: "Revenue",
  cost: "Cost",
  speed: "Speed",
  quality: "Quality",
  risk: "Risk",
  adoption: "Adoption",
};

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function display(metric: ValueMetric) {
  if (metric.value === null) return "Not measured";
  const value = Number(metric.value);
  if (metric.unit === "ratio") return `${(value * 100).toFixed(1)}%`;
  if (metric.unit === "currency" || /^[A-Z]{3}$/.test(metric.unit)) {
    return new Intl.NumberFormat("en-NG", {
      style: "currency",
      currency: metric.unit === "currency" ? "NGN" : metric.unit,
      maximumFractionDigits: 2,
    }).format(value);
  }
  if (metric.unit === "minutes") return `${value.toFixed(1)} min`;
  return value.toLocaleString();
}

export default async function ValuePage() {
  const business = await activeBusiness();
  if (!business) {
    return <div className="p-8">Create a business workspace to measure workflow value.</div>;
  }
  const dashboard = await beoApi.valueDashboard(business.id);
  return (
    <div className="mx-auto max-w-[1500px] px-4 py-8 sm:px-5 md:px-8">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#90948f]">
        {business.name}
      </p>
      <div className="mt-1 flex items-start gap-3">
        <div className="grid size-11 place-items-center rounded-2xl bg-orange-50 text-[#ed633f]">
          <Gauge className="size-5" />
        </div>
        <div>
          <h1 className="text-3xl font-bold tracking-[-0.035em]">Business value</h1>
          <p className="mt-1 text-sm text-[#747973]">
            Measured workflow evidence compared with clearly labelled onboarding estimates.
          </p>
        </div>
      </div>

      {dashboard.evidence.workflow_runs === 0 && (
        <Card className="mt-6 p-5">
          <h2 className="font-bold">No workflow evidence yet</h2>
          <p className="mt-2 text-sm leading-6 text-[#747973]">
            Business value measures the commission enquiry workflow. Metrics will appear as
            enquiries are processed and outcomes are recorded. Existing quotes and inbox activity
            can be viewed in Analytics.
          </p>
        </Card>
      )}
      {dashboard.baseline && (
        <Card className="mt-6 flex flex-wrap items-center gap-3 p-4">
          <Badge className="bg-amber-50 text-amber-800">User estimate</Badge>
          <p className="text-sm text-[#5f655f]">
            Baseline values were supplied during onboarding and are not measured facts.
          </p>
        </Card>
      )}

      <div className="mt-6 grid gap-5 xl:grid-cols-2">
        {Object.entries(dashboard.categories).map(([category, metrics]) => (
          <Card key={category} className="p-5">
            <h2 className="text-lg font-bold">
              {categoryLabels[category as keyof typeof categoryLabels]}
            </h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {metrics.length ? (
                metrics.map((metric) => (
                  <div key={metric.key} className="rounded-2xl border p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.1em] text-[#90948f]">
                      {label(metric.key)}
                    </p>
                    <p className="mt-2 text-2xl font-bold">{display(metric)}</p>
                    {metric.improvement && (
                      <p className="mt-1 text-xs font-semibold text-emerald-700">
                        {(Number(metric.improvement) * 100).toFixed(1)}% versus estimate
                      </p>
                    )}
                  </div>
                ))
              ) : (
                <p className="text-sm text-[#747973]">No measured evidence yet.</p>
              )}
            </div>
          </Card>
        ))}
      </div>

      <Card className="mt-5 flex items-start gap-3 p-5">
        <Activity className="mt-0.5 size-5 text-[#ed633f]" />
        <p className="text-sm leading-6 text-[#5f655f]">
          Evidence: {dashboard.evidence.workflow_runs} workflow runs,{" "}
          {dashboard.evidence.outcomes} outcomes, {dashboard.evidence.approval_records} approval
          records, and {dashboard.evidence.corrections} corrections.
        </p>
      </Card>
    </div>
  );
}

import { Code2 } from "lucide-react";
import { Card } from "@/components/ui/card";

export function WebsiteFormCard({
  businessSlug,
  formKey,
}: {
  businessSlug: string;
  formKey: string;
}) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
  const endpoint = `${apiUrl}/forms/${businessSlug}/lead`;
  const example = `fetch("${endpoint}", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    form_key: "${formKey}",
    name: "Client name",
    email: "client@example.com",
    phone: "090...",
    service: "Portrait",
    budget: "NGN 250,000",
    deadline: "Next week",
    message: "I want a family portrait.",
    source_url: window.location.href
  })
});`;

  return (
    <Card className="p-5 md:col-span-2">
      <div className="flex items-start gap-3">
        <div className="grid size-10 place-items-center rounded-xl bg-blue-50 text-blue-700">
          <Code2 className="size-4" />
        </div>
        <div>
          <h2 className="font-bold">Website form inbox trigger</h2>
          <p className="mt-1 text-sm leading-6 text-[#777c76]">
            Website forms can now create BeoOS inbox threads for this business. Keep the form key private in your form handler or protected site code.
          </p>
        </div>
      </div>
      <div className="mt-5 grid gap-3 text-sm">
        <div className="rounded-xl bg-[#f7f6f2] p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-[#858a84]">Endpoint</p>
          <p className="mt-1 break-all font-mono text-xs text-[#252a33]">{endpoint}</p>
        </div>
        <div className="rounded-xl bg-[#f7f6f2] p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-[#858a84]">Tenant form key</p>
          <p className="mt-1 break-all font-mono text-xs text-[#252a33]">{formKey || "Run the latest backend seed to generate this key."}</p>
        </div>
        <pre className="overflow-x-auto rounded-xl bg-[#101827] p-4 text-xs leading-6 text-white/80">
          <code>{example}</code>
        </pre>
      </div>
    </Card>
  );
}

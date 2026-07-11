import { ArrowLeft, Bot, CheckCircle2, Clock, Mail, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { CreateLeadButton } from "@/components/dashboard/create-lead-button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { activeBusiness, beoApi, type ThreadDetail } from "@/lib/api";

export const metadata = { title: "Email thread" };

const categoryStyles: Record<string, string> = {
  portrait: "bg-violet-50 text-violet-700",
  mural: "bg-sky-50 text-sky-700",
  live_painting: "bg-amber-50 text-amber-700",
  art_school: "bg-emerald-50 text-emerald-700",
  existing_client: "bg-blue-50 text-blue-700",
  corporate: "bg-slate-100 text-slate-700",
  urgent: "bg-red-50 text-red-700",
  spam: "bg-zinc-100 text-zinc-500",
  general: "bg-orange-50 text-orange-700",
};

export default async function EmailThreadPage({
  params,
}: {
  params: Promise<{ threadId: string }>;
}) {
  let detail: ThreadDetail | null = null;
  let businessId: string | null = null;
  const { threadId } = await params;

  try {
    const business = await activeBusiness();
    if (business) {
      businessId = business.id;
      detail = await beoApi.thread(business.id, threadId);
    }
  } catch {
    detail = null;
  }

  if (!detail) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8 md:px-8">
        <Link href="/dashboard/inbox" className="inline-flex items-center gap-2 text-sm text-[#747973] hover:text-[#171b23]">
          <ArrowLeft className="size-4" /> Back to inbox
        </Link>
        <Card className="mt-6 p-8 text-center">
          <Mail className="mx-auto size-8 text-[#ed633f]" />
          <h1 className="mt-3 text-lg font-bold">Thread could not be loaded</h1>
          <p className="mt-1 text-sm text-[#747973]">Refresh the inbox or confirm your Railway API is on the latest deployment.</p>
        </Card>
      </div>
    );
  }

  const latestDraft = detail.drafts[0];

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 md:px-8">
      <Link href="/dashboard/inbox" className="inline-flex items-center gap-2 text-sm text-[#747973] hover:text-[#171b23]">
        <ArrowLeft className="size-4" /> Back to inbox
      </Link>

      <header className="mt-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge className={categoryStyles[detail.thread.category] ?? categoryStyles.general}>
            {detail.thread.category.replaceAll("_", " ")}
          </Badge>
          <Badge className="bg-slate-100 text-slate-700">{detail.thread.status.replaceAll("_", " ")}</Badge>
          {detail.thread.is_deal && <Badge className="bg-emerald-50 text-emerald-700">deal signal</Badge>}
        </div>
        <h1 className="mt-3 text-2xl font-bold tracking-[-0.035em] text-[#171b23] sm:text-3xl">{detail.thread.subject}</h1>
        <p className="mt-1 text-sm text-[#747973]">
          {detail.thread.contact_name || "Unknown sender"} · {detail.thread.contact_email || "No email"}
        </p>
      </header>

      <div className="mt-7 grid gap-5 lg:grid-cols-[1fr_360px]">
        <section className="space-y-4">
          {detail.messages.map((message) => (
            <Card key={message.id} className="overflow-hidden">
              <div className="flex flex-col gap-2 border-b bg-[#fbfaf7] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-bold">{message.sender_name || message.sender_email}</p>
                  <p className="text-xs text-[#7d827d]">{message.sender_email}</p>
                </div>
                <p className="flex items-center gap-1.5 text-xs text-[#7d827d]">
                  <Clock className="size-3.5" />
                  {new Date(message.sent_at).toLocaleString()}
                </p>
              </div>
              <div className="p-5">
                <p className="whitespace-pre-wrap text-sm leading-7 text-[#31363d]">{message.body_text || "(No readable message body)"}</p>
              </div>
            </Card>
          ))}
        </section>

        <aside className="space-y-4">
          {businessId && (
            <Card className="p-5">
              <h2 className="font-bold">CRM</h2>
              <p className="mt-2 text-sm leading-6 text-[#747973]">
                Convert this conversation into a sales lead so it appears in the CRM pipeline.
              </p>
              <div className="mt-4">
                <CreateLeadButton businessId={businessId} threadId={detail.thread.id} isDeal={detail.thread.is_deal} />
              </div>
            </Card>
          )}

          <Card className="p-5">
            <div className="flex items-center gap-2">
              <Bot className="size-4 text-[#ed633f]" />
              <h2 className="font-bold">AI handling</h2>
            </div>
            <dl className="mt-4 space-y-3 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-[#747973]">Priority</dt>
                <dd className="font-semibold">{detail.thread.priority}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-[#747973]">Professional</dt>
                <dd className="font-semibold">{detail.thread.is_professional ? "Yes" : "No"}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-[#747973]">Unread</dt>
                <dd className="font-semibold">{detail.thread.unread_count}</dd>
              </div>
            </dl>
          </Card>

          {latestDraft ? (
            <Card className="p-5">
              <div className="flex items-center gap-2">
                {latestDraft.auto_send_eligible ? <CheckCircle2 className="size-4 text-emerald-600" /> : <ShieldAlert className="size-4 text-amber-600" />}
                <h2 className="font-bold">AI draft</h2>
              </div>
              <p className="mt-2 text-xs uppercase tracking-wide text-[#90948f]">{latestDraft.status} · {latestDraft.draft_type.replaceAll("_", " ")}</p>
              <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-[#373c43]">{latestDraft.body_text}</p>
              {latestDraft.policy_reasons.length > 0 && (
                <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3">
                  <p className="text-xs font-bold text-amber-900">Needs your review</p>
                  <ul className="mt-2 space-y-1 text-xs text-amber-900/75">
                    {latestDraft.policy_reasons.map((reason) => <li key={reason}>• {reason}</li>)}
                  </ul>
                </div>
              )}
            </Card>
          ) : (
            <Card className="p-5">
              <div className="flex items-center gap-2">
                <Bot className="size-4 text-[#ed633f]" />
                <h2 className="font-bold">AI draft</h2>
              </div>
              <p className="mt-3 text-sm leading-6 text-[#747973]">
                This message is stored, but no draft is attached yet. For old imported mail, BeoOS marks it as history; new inbound mail is where the AI drafts and routes responses.
              </p>
            </Card>
          )}
        </aside>
      </div>
    </div>
  );
}

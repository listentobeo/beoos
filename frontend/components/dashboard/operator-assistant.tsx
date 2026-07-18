"use client";

import { Bot, ChevronDown, LoaderCircle, Send, Sparkles, X } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type OperatorAction = {
  label: string;
  kind: "read_only" | "needs_confirmation" | "future_tool";
  reason: string;
  tool_name: string | null;
  payload: Record<string, unknown>;
};

type OperatorResponse = {
  success: boolean;
  answer: string;
  summary: string[];
  recommended_actions: OperatorAction[];
  read_only_tools_used: string[];
  warnings: string[];
};

type ChatMessage = {
  role: "user" | "operator";
  content: string;
  response?: OperatorResponse;
};

const API_URL = "/api/beoos";

const quickPrompts = [
  "What needs my attention today?",
  "Which leads should I follow up?",
  "How healthy is my quote pipeline?",
  "What should I improve in marketing?",
];

function inferMode(message: string) {
  const lower = message.toLowerCase();
  if (lower.includes("quote") || lower.includes("quotation")) return "quotes";
  if (lower.includes("lead") || lower.includes("crm") || lower.includes("client")) return "crm";
  if (lower.includes("price") || lower.includes("catalogue") || lower.includes("stock")) {
    return "pricing";
  }
  if (lower.includes("marketing") || lower.includes("search console") || lower.includes("blog")) {
    return "marketing";
  }
  if (lower.includes("analytics") || lower.includes("report")) return "analytics";
  if (lower.includes("inbox") || lower.includes("message") || lower.includes("email")) {
    return "inbox";
  }
  return "general";
}

export function OperatorAssistant({ businessId }: { businessId: string | null }) {
  const [open, setOpen] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const disabled = !businessId;

  const latestWarning = useMemo(
    () => messages.toReversed().find((item) => item.response?.warnings.length)?.response?.warnings[0],
    [messages],
  );

  async function ask(message: string) {
    if (!businessId || !message.trim()) return;
    const clean = message.trim();
    setInput("");
    setLoading(true);
    setMessages((items) => [...items, { role: "user", content: clean }]);
    try {
      const conversation_context = messages.slice(-6).map((item) => ({
        role: item.role,
        content: item.content,
      }));
      const response = await fetch(`${API_URL}/businesses/${businessId}/operator/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: clean,
          mode: inferMode(clean),
          conversation_context,
        }),
      });
      const result = (await response.json().catch(() => ({}))) as Partial<OperatorResponse> & {
        detail?: string;
      };
      if (!response.ok || !result.answer) {
        throw new Error(result.detail ?? `Operator request failed (${response.status})`);
      }
      setMessages((items) => [
        ...items,
        { role: "operator", content: result.answer ?? "", response: result as OperatorResponse },
      ]);
    } catch (error) {
      setMessages((items) => [
        ...items,
        {
          role: "operator",
          content:
            error instanceof Error
              ? error.message
              : "The operator could not answer right now. Try again shortly.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void ask(input);
  }

  if (disabled) {
    return null;
  }

  return (
    <div className="fixed bottom-5 right-5 z-40 hidden lg:block">
      {open && (
        <div
          className={cn(
            "mb-4 w-[390px] overflow-hidden rounded-3xl border border-[#e8dfd7] bg-white shadow-[0_24px_80px_rgba(15,23,42,0.22)] transition",
            minimized ? "h-[72px]" : "h-[620px]",
          )}
        >
          <div className="flex items-center gap-3 border-b bg-[#101827] px-4 py-3 text-white">
            <div className="grid size-10 place-items-center rounded-2xl bg-[#ed633f]">
              <Bot className="size-5" />
            </div>
            <div className="min-w-0">
              <p className="font-black tracking-[-0.03em]">BeoOS Operator</p>
              <p className="truncate text-xs text-white/55">Read, reason, and plan across this tenant</p>
            </div>
            <button
              type="button"
              onClick={() => setMinimized((value) => !value)}
              className="ml-auto rounded-full p-2 text-white/70 hover:bg-white/10 hover:text-white"
              aria-label={minimized ? "Expand operator" : "Minimize operator"}
            >
              <ChevronDown className={cn("size-4 transition", minimized && "rotate-180")} />
            </button>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-full p-2 text-white/70 hover:bg-white/10 hover:text-white"
              aria-label="Close operator"
            >
              <X className="size-4" />
            </button>
          </div>

          {!minimized && (
            <div className="flex h-[548px] flex-col">
              <div className="min-h-0 flex-1 space-y-3 overflow-y-auto bg-[#faf8f4] p-4">
                {messages.length === 0 ? (
                  <div className="rounded-3xl border bg-white p-4">
                    <Sparkles className="size-5 text-[#ed633f]" />
                    <h3 className="mt-3 font-black">Ask BeoOS to inspect the business.</h3>
                    <p className="mt-2 text-sm leading-6 text-[#667085]">
                      This first operator version reads your inbox, CRM, quotes, prices, marketing,
                      and analytics context. Write actions will be added behind approvals next.
                    </p>
                    <div className="mt-4 grid gap-2">
                      {quickPrompts.map((prompt) => (
                        <button
                          key={prompt}
                          type="button"
                          onClick={() => void ask(prompt)}
                          className="rounded-2xl border bg-[#fffaf7] px-3 py-2 text-left text-xs font-bold text-[#384252] transition hover:border-[#ed633f]/40 hover:bg-orange-50"
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  messages.map((message, index) => (
                    <div
                      key={`${message.role}-${index}`}
                      className={cn(
                        "rounded-3xl px-4 py-3 text-sm leading-6",
                        message.role === "user"
                          ? "ml-8 bg-[#ed633f] text-white"
                          : "mr-8 border bg-white text-[#26303f]",
                      )}
                    >
                      <p className="whitespace-pre-wrap">{message.content}</p>
                      {message.response?.summary?.length ? (
                        <ul className="mt-3 space-y-1 border-t pt-3 text-xs text-[#667085]">
                          {message.response.summary.slice(0, 4).map((item) => (
                            <li key={item}>• {item}</li>
                          ))}
                        </ul>
                      ) : null}
                      {message.response?.recommended_actions?.length ? (
                        <div className="mt-3 space-y-2">
                          {message.response.recommended_actions.slice(0, 3).map((action) => (
                            <div key={`${action.label}-${action.kind}`} className="rounded-2xl bg-[#f8f5ef] p-3">
                              <div className="flex items-start justify-between gap-2">
                                <p className="text-xs font-black">{action.label}</p>
                                <Badge className="bg-white text-[#6b7280]">{action.kind.replace("_", " ")}</Badge>
                              </div>
                              <p className="mt-1 text-xs leading-5 text-[#667085]">{action.reason}</p>
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ))
                )}
                {loading && (
                  <div className="mr-8 flex items-center gap-2 rounded-3xl border bg-white px-4 py-3 text-sm text-[#667085]">
                    <LoaderCircle className="size-4 animate-spin text-[#ed633f]" />
                    Reading BeoOS context…
                  </div>
                )}
              </div>

              {latestWarning && (
                <p className="border-t bg-amber-50 px-4 py-2 text-xs text-amber-800">{latestWarning}</p>
              )}
              <form onSubmit={submit} className="flex items-center gap-2 border-t bg-white p-3">
                <input
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder="Ask about leads, quotes, prices, reports…"
                  className="min-w-0 flex-1 rounded-2xl border bg-[#fbfaf8] px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-[#ed633f]/20"
                />
                <Button type="submit" disabled={loading || !input.trim()} size="icon" aria-label="Ask operator">
                  {loading ? <LoaderCircle className="size-4 animate-spin" /> : <Send className="size-4" />}
                </Button>
              </form>
            </div>
          )}
        </div>
      )}

      <button
        type="button"
        onClick={() => {
          setOpen(true);
          setMinimized(false);
        }}
        className="group flex items-center gap-3 rounded-full bg-[#101827] px-4 py-3 text-sm font-black text-white shadow-[0_18px_50px_rgba(15,23,42,0.28)] transition hover:-translate-y-0.5 hover:bg-[#ed633f]"
      >
        <span className="grid size-9 place-items-center rounded-full bg-[#ed633f] transition group-hover:bg-white group-hover:text-[#ed633f]">
          <Sparkles className="size-4" />
        </span>
        Ask BeoOS
      </button>
    </div>
  );
}

"use client";

import { Download, Mail, MessageCircleMore, Phone, Trash2, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import type { ClientContact } from "@/lib/api";

const API_URL = "/api/beoos";

function downloadFile(filename: string, contents: string) {
  const blob = new Blob([contents], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function csvCell(value: string | null | undefined) {
  const text = String(value ?? "");
  return `"${text.replaceAll('"', '""')}"`;
}

export function ClientDirectory({
  businessId,
  clients,
}: {
  businessId: string;
  clients: ClientContact[];
}) {
  const router = useRouter();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const selectedClients = useMemo(
    () => clients.filter((client) => selected.has(client.id)),
    [clients, selected],
  );
  const exportPool = selectedClients.length ? selectedClients : clients;

  function toggle(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    setSelected((current) => {
      if (current.size === clients.length) return new Set();
      return new Set(clients.map((client) => client.id));
    });
  }

  function exportContacts(type: "emails" | "phones" | "full") {
    const rows =
      type === "emails"
        ? [["name", "email"], ...exportPool.filter((client) => client.email).map((client) => [client.name ?? "", client.email])]
        : type === "phones"
          ? [["name", "phone"], ...exportPool.filter((client) => client.phone).map((client) => [client.name ?? "", client.phone ?? ""])]
          : [
              ["name", "email", "phone", "channel", "threads", "messages", "latest_request"],
              ...exportPool.map((client) => [
                client.name ?? "",
                client.email,
                client.phone ?? "",
                client.latest_channel ?? client.preferred_channel,
                String(client.thread_count),
                String(client.message_count),
                client.latest_thread_subject ?? "",
              ]),
            ];
    downloadFile(
      `beoos-clients-${type}.csv`,
      rows.map((row) => row.map(csvCell).join(",")).join("\n"),
    );
  }

  async function deleteSelected() {
    if (selected.size === 0) return;
    const confirmed = window.confirm(
      `Delete ${selected.size} selected client${selected.size === 1 ? "" : "s"} from the client directory? Their message history will stay in BeoOS.`,
    );
    if (!confirmed) return;
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch(`${API_URL}/businesses/${businessId}/email/clients`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contact_ids: Array.from(selected) }),
      });
      if (!response.ok) throw new Error("Selected clients could not be deleted.");
      const payload = (await response.json()) as { deleted?: number };
      setSelected(new Set());
      setMessage(`${payload.deleted ?? 0} client${payload.deleted === 1 ? "" : "s"} deleted.`);
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Selected clients could not be deleted.");
    } finally {
      setBusy(false);
    }
  }

  if (clients.length === 0) {
    return (
      <div className="grid min-h-72 place-items-center p-8 text-center">
        <div>
          <div className="mx-auto grid size-12 place-items-center rounded-2xl bg-[#fff0ea] text-[#ed633f]">
            <UserRound className="size-5" />
          </div>
          <h3 className="mt-4 text-sm font-bold">No client contacts yet</h3>
          <p className="mt-1 max-w-sm text-sm leading-relaxed text-[#727771]">
            BeoOS will collect client names, emails, and phone numbers from forms, email, and WhatsApp conversations.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex flex-col gap-3 border-b bg-[#fbfaf7] px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-base font-bold">Client directory</h2>
          <p className="mt-1 text-xs text-[#777c76]">
            Select rows, export emails or phone numbers, and jump back into the latest client thread.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => exportContacts("emails")}>
            <Download className="size-4" />
            Export emails
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={() => exportContacts("phones")}>
            <Download className="size-4" />
            Export numbers
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={() => exportContacts("full")}>
            <Download className="size-4" />
            Export full CSV
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="border-red-100 text-red-700 hover:bg-red-50"
            onClick={deleteSelected}
            disabled={busy || selected.size === 0}
          >
            <Trash2 className="size-4" />
            Delete selected
          </Button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[860px] text-left text-sm">
          <thead className="border-b bg-white text-[11px] font-black uppercase tracking-[0.14em] text-[#9aa09a]">
            <tr>
              <th className="w-12 px-5 py-3">
                <input
                  type="checkbox"
                  checked={selected.size === clients.length}
                  onChange={toggleAll}
                  aria-label="Select all clients"
                />
              </th>
              <th className="px-3 py-3">Client</th>
              <th className="px-3 py-3">Latest request</th>
              <th className="px-3 py-3">Activity</th>
              <th className="px-5 py-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {clients.map((client) => (
              <tr key={client.id} className="bg-white transition hover:bg-[#fbfaf7]">
                <td className="px-5 py-4 align-top">
                  <input
                    type="checkbox"
                    checked={selected.has(client.id)}
                    onChange={() => toggle(client.id)}
                    aria-label={`Select ${client.name || client.email}`}
                  />
                </td>
                <td className="px-3 py-4 align-top">
                  <div className="flex items-start gap-3">
                    <div className="grid size-10 shrink-0 place-items-center rounded-2xl bg-[#fff0ea] text-sm font-black text-[#ed633f]">
                      {(client.name || client.email).slice(0, 1).toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <p className="truncate font-black text-[#171b23]">{client.name || "Unnamed client"}</p>
                      <div className="mt-1 space-y-1 text-xs text-[#727771]">
                        <p className="flex items-center gap-1.5">
                          <Mail className="size-3.5" />
                          {client.email}
                        </p>
                        <p className="flex items-center gap-1.5">
                          <Phone className="size-3.5" />
                          {client.phone || "No phone captured"}
                        </p>
                      </div>
                    </div>
                  </div>
                </td>
                <td className="max-w-sm px-3 py-4 align-top">
                  <p className="truncate font-semibold text-[#252a33]">
                    {client.latest_thread_subject || "No thread yet"}
                  </p>
                  <p className="mt-1 text-xs text-[#7d827d]">
                    {client.latest_channel || client.preferred_channel} channel
                  </p>
                </td>
                <td className="px-3 py-4 align-top text-xs text-[#727771]">
                  <p className="font-semibold text-[#252a33]">{client.thread_count} thread{client.thread_count === 1 ? "" : "s"}</p>
                  <p>{client.message_count} message{client.message_count === 1 ? "" : "s"}</p>
                  {client.is_existing_client && <p className="mt-1 font-bold text-blue-700">Existing client</p>}
                </td>
                <td className="px-5 py-4 text-right align-top">
                  {client.latest_thread_id ? (
                    <Button asChild variant="outline" size="sm">
                      <Link href={`/dashboard/inbox/${client.latest_thread_id}`}>
                        <MessageCircleMore className="size-4" />
                        View client thread
                      </Link>
                    </Button>
                  ) : (
                    <span className="text-xs text-[#9aa09a]">No thread</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {message && <p className="border-t px-5 py-3 text-xs text-[#747973]">{message}</p>}
    </div>
  );
}

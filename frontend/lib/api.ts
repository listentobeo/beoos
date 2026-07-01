import { auth } from "@clerk/nextjs/server";
import { cookies } from "next/headers";

export type Business = {
  id: string;
  slug: string;
  name: string;
  primary_email: string;
  whatsapp_number: string;
  reply_signature: string;
  role: string;
};
export type InboxStats = {
  unread: number;
  needs_approval: number;
  urgent: number;
  routed_whatsapp: number;
  existing_clients: number;
};
export type Thread = {
  id: string;
  subject: string;
  contact_name: string | null;
  contact_email: string | null;
  category: string;
  status: string;
  priority: number;
  is_deal: boolean;
  is_professional: boolean;
  unread_count: number;
  latest_message_at: string;
};
export type DraftQueueItem = {
  id: string;
  thread_id: string;
  thread_subject: string;
  subject: string;
  body_text: string;
  status: string;
  draft_type: string;
  auto_send_eligible: boolean;
  policy_reasons: string[];
  category: string;
  contact_name: string | null;
  contact_email: string | null;
  created_at: string;
};
export type PriceItem = {
  id: string;
  service: string;
  label: string;
  amount_min: string | null;
  amount_max: string | null;
  currency: string;
  source_url: string;
  effective_from: string;
  effective_until: string | null;
  active: boolean;
  approved_by: string;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const { getToken } = await auth();
  const token = await getToken();
  if (!token) throw new Error("You are not signed in");
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { ...init?.headers, Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`BeoOS API request failed (${response.status})`);
  return response.json() as Promise<T>;
}

export const beoApi = {
  businesses: () => apiFetch<Business[]>("/businesses"),
  stats: (businessId: string) => apiFetch<InboxStats>(`/businesses/${businessId}/email/stats`),
  threads: (businessId: string, filters?: { category?: string; status?: string }) => {
    const params = new URLSearchParams(filters);
    const suffix = params.size ? `?${params.toString()}` : "";
    return apiFetch<Thread[]>(`/businesses/${businessId}/email/threads${suffix}`);
  },
  drafts: (businessId: string) =>
    apiFetch<DraftQueueItem[]>(`/businesses/${businessId}/email/drafts`),
  prices: (businessId: string) =>
    apiFetch<PriceItem[]>(`/businesses/${businessId}/prices`),
};

export async function activeBusiness(existingBusinesses?: Business[]) {
  const businesses = existingBusinesses ?? (await beoApi.businesses());
  const selectedId = (await cookies()).get("beoos_business_id")?.value;
  return businesses.find((business) => business.id === selectedId) ?? businesses[0] ?? null;
}

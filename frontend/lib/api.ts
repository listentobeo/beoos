import { auth } from "@clerk/nextjs/server";
import { cookies } from "next/headers";
import { cache } from "react";

export type BusinessAIPolicy = {
  auto_acknowledge: boolean;
  auto_route_whatsapp: boolean;
  confidence_threshold: number;
  require_approval_for_prices: boolean;
  require_approval_for_commitments: boolean;
  require_approval_for_risk_flags: boolean;
  existing_clients_stay_on_current_channel: boolean;
  art_school_stays_in_email: boolean;
  professionals_stay_in_email: boolean;
  route_only_deals_to_whatsapp: boolean;
  custom_instructions: string;
};

export type BusinessWhatsAppSettings = {
  enabled: boolean;
  phone_number_id: string;
  business_account_id: string;
  display_phone_number: string;
};

export type Business = {
  id: string;
  slug: string;
  name: string;
  primary_email: string;
  whatsapp_number: string;
  reply_signature: string;
  timezone: string;
  role: string;
  ai_policy: BusinessAIPolicy;
  whatsapp_connection: BusinessWhatsAppSettings;
  website_form_key: string;
};
export type InboxStats = {
  unread: number;
  needs_approval: number;
  urgent: number;
  routed_whatsapp: number;
  existing_clients: number;
};
export type MailboxStatus = {
  connected: boolean;
  provider: string | null;
  email_address: string | null;
  active: boolean;
  history_start_at: string | null;
  last_synced_at: string | null;
  sync_lease_until: string | null;
  thread_count: number;
  message_count: number;
  auto_sync_enabled: boolean;
  auto_sync_interval_seconds: number;
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
export type ThreadMessage = {
  id: string;
  direction: string;
  sender_email: string;
  sender_name: string | null;
  subject: string;
  body_text: string;
  sent_at: string;
};
export type DraftView = {
  id: string;
  subject: string;
  body_text: string;
  status: string;
  draft_type: string;
  auto_send_eligible: boolean;
  policy_reasons: string[];
};
export type ThreadDetail = {
  thread: Thread;
  messages: ThreadMessage[];
  drafts: DraftView[];
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

export type PushStatus = {
  enabled: boolean;
  vapid_public_key: string;
};

export type CRMLead = {
  id: string;
  business_id: string;
  contact_id: string | null;
  thread_id: string | null;
  title: string;
  stage: string;
  source: string;
  service: string | null;
  budget: string | null;
  deadline: string | null;
  estimated_value: string | null;
  currency: string;
  probability: number;
  lead_score: number;
  temperature: "hot" | "warm" | "cold";
  qualification_summary: string;
  qualification_reasons: string[];
  last_qualified_at: string | null;
  next_follow_up_at: string | null;
  notes: string;
  owner_id: string | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  thread_subject: string | null;
};

export type CRMStats = {
  total: number;
  open: number;
  won: number;
  lost: number;
  estimated_open_value: string;
  needs_follow_up: number;
};

export type QuoteStatus =
  | "draft"
  | "needs_approval"
  | "approved"
  | "sent"
  | "accepted"
  | "rejected"
  | "expired";

export type QuoteTemplateType = "mural" | "custom";

export type Quote = {
  id: string;
  business_id: string;
  lead_id: string | null;
  contact_id: string | null;
  title: string;
  template_type: QuoteTemplateType;
  status: QuoteStatus;
  currency: string;
  subtotal: string;
  total: string;
  deposit_required: string | null;
  public_url: string | null;
  valid_until: string | null;
  input_data: Record<string, unknown>;
  calculation: Record<string, unknown>;
  proposal: Record<string, unknown>;
  internal_notes: string;
  approved_by: string | null;
  sent_at: string | null;
  client_viewed_at: string | null;
  accepted_at: string | null;
  payment_url: string | null;
  payment_reference: string | null;
  created_at: string;
  updated_at: string;
  lead_title: string | null;
  contact_name: string | null;
  contact_email: string | null;
};

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

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

const getBusinesses = cache(() => apiFetch<Business[]>("/businesses"));

export const beoApi = {
  businesses: getBusinesses,
  stats: (businessId: string) => apiFetch<InboxStats>(`/businesses/${businessId}/email/stats`),
  mailbox: (businessId: string, provider?: string) =>
    apiFetch<MailboxStatus>(
      `/businesses/${businessId}/email/mailbox${provider ? `?provider=${provider}` : ""}`,
    ),
  threads: (
    businessId: string,
    filters?: { category?: string; status?: string; provider?: string; search?: string },
  ) => {
    const params = new URLSearchParams();
    Object.entries(filters ?? {}).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    const suffix = params.size ? `?${params.toString()}` : "";
    return apiFetch<Thread[]>(`/businesses/${businessId}/email/threads${suffix}`);
  },
  thread: (businessId: string, threadId: string) =>
    apiFetch<ThreadDetail>(`/businesses/${businessId}/email/threads/${threadId}`),
  drafts: (businessId: string) =>
    apiFetch<DraftQueueItem[]>(`/businesses/${businessId}/email/drafts`),
  pushStatus: (businessId: string) =>
    apiFetch<PushStatus>(`/businesses/${businessId}/notifications/push`),
  crmLeads: (businessId: string) => apiFetch<CRMLead[]>(`/businesses/${businessId}/crm/leads`),
  crmStats: (businessId: string) => apiFetch<CRMStats>(`/businesses/${businessId}/crm/stats`),
  quotes: (businessId: string) => apiFetch<Quote[]>(`/businesses/${businessId}/quotes`),
  quote: (businessId: string, quoteId: string) =>
    apiFetch<Quote>(`/businesses/${businessId}/quotes/${quoteId}`),
  quotePaymentLink: (businessId: string, quoteId: string) =>
    apiFetch<Quote>(`/businesses/${businessId}/quotes/${quoteId}/payment-link`, {
      method: "POST",
    }),
  prices: (businessId: string) =>
    apiFetch<PriceItem[]>(`/businesses/${businessId}/prices`),
};

export async function activeBusiness(existingBusinesses?: Business[]) {
  const businesses = existingBusinesses ?? (await beoApi.businesses());
  const selectedId = (await cookies()).get("beoos_business_id")?.value;
  return businesses.find((business) => business.id === selectedId) ?? businesses[0] ?? null;
}


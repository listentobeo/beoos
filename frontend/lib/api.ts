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
  connected_via: string;
  connected_at: string;
  token_configured: boolean;
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
  attachment_metadata: Array<Record<string, unknown>>;
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
  stock_quantity: number | null;
  custom_fields: Record<string, string | number | boolean | null>;
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

export type DashboardSummary = {
  business: Business;
  inbox_stats: InboxStats;
  threads: Thread[];
  mailbox: MailboxStatus;
  zoho_mailbox: MailboxStatus;
  gmail_mailbox: MailboxStatus;
  push_status: PushStatus;
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

export type AnalyticsBucket = {
  key: string;
  label: string;
  count: number;
  value: string | null;
};

export type AnalyticsTotals = {
  conversations: number;
  inbound_messages: number;
  outbound_messages: number;
  unread_messages: number;
  needs_approval: number;
  leads: number;
  quotes: number;
  pending_drafts: number;
  due_followups: number;
};

export type AnalyticsConversion = {
  leads_created: number;
  quotes_created: number;
  quotes_accepted: number;
  lead_to_quote_rate: number;
  quote_acceptance_rate: number;
  open_quote_value: string;
  accepted_quote_value: string;
};

export type AnalyticsRecentActivity = {
  label: string;
  detail: string;
  occurred_at: string;
  href: string | null;
};

export type AnalyticsSummary = {
  window_days: number;
  totals: AnalyticsTotals;
  conversion: AnalyticsConversion;
  inbox_by_provider: AnalyticsBucket[];
  thread_statuses: AnalyticsBucket[];
  lead_sources: AnalyticsBucket[];
  lead_stages: AnalyticsBucket[];
  lead_temperatures: AnalyticsBucket[];
  quote_statuses: AnalyticsBucket[];
  follow_up_statuses: AnalyticsBucket[];
  recent_activity: AnalyticsRecentActivity[];
};

export type MarketingSource = "search_console" | "blogger" | "clarity" | "website" | "manual";

export type MarketingTotal = {
  source: string;
  rows: number;
  impressions: number;
  clicks: number;
  sessions: number;
  leads: number;
};

export type MarketingPageOpportunity = {
  page_url: string;
  title: string;
  impressions: number;
  clicks: number;
  sessions: number;
  leads: number;
  ctr: number;
  average_position: number | null;
  recommendation: string;
};

export type MarketingQueryOpportunity = {
  query: string;
  page_url: string;
  impressions: number;
  clicks: number;
  ctr: number;
  average_position: number | null;
  recommendation: string;
};

export type MarketingContentCluster = {
  topic: string;
  impressions: number;
  clicks: number;
  queries: string[];
  recommended_angle: string;
};

export type MarketingActionItem = {
  priority: "high" | "medium" | "low";
  source: string;
  label: string;
  reason: string;
  recommended_action: string;
  page_url: string | null;
};

export type MarketingMetricView = {
  id: string;
  source: string;
  page_url: string;
  query: string;
  title: string;
  impressions: number;
  clicks: number;
  sessions: number;
  leads: number;
  ctr: string | null;
  average_position: string | null;
  engagement_rate: string | null;
  avg_time_seconds: string | null;
  scroll_depth: string | null;
  metric_date: string | null;
  created_at: string;
};

export type MarketingSummary = {
  window_days: number;
  totals: MarketingTotal[];
  top_pages: MarketingPageOpportunity[];
  query_opportunities: MarketingQueryOpportunity[];
  content_clusters: MarketingContentCluster[];
  action_items: MarketingActionItem[];
  recent_metrics: MarketingMetricView[];
};

export type MarketingImportResponse = {
  success: boolean;
  source: string;
  rows_received: number;
  rows_created: number;
  duplicates_skipped: number;
};

export type DailyReportSettings = {
  enabled: boolean;
  time: string;
  timezone: string;
  email: string | null;
  push_enabled: boolean;
  last_sent_on: string | null;
  last_sent_at: string | null;
};

export type DailyReportTotals = {
  inbound_messages: number;
  unread_messages: number;
  whatsapp_messages: number;
  needs_approval: number;
  leads_created: number;
  hot_leads: number;
  quotes_created: number;
  quotes_accepted: number;
  followups_due: number;
  pending_drafts: number;
  open_quote_value: string;
  accepted_quote_value: string;
};

export type DailyReportPreview = {
  business_id: string;
  business_name: string;
  report_date: string;
  timezone: string;
  recipient: string;
  subject: string;
  totals: DailyReportTotals;
  highlights: string[];
  action_items: string[];
  recent_activity: AnalyticsRecentActivity[];
};

export type DailyReportSendResult = {
  success: boolean;
  email_sent: boolean;
  push_sent: number;
  recipient: string;
  subject: string;
  message: string;
  preview: DailyReportPreview;
};

export type FollowUpTask = {
  id: string;
  business_id: string;
  lead_id: string;
  thread_id: string | null;
  contact_id: string | null;
  sequence_name: string;
  step_number: number;
  channel: string;
  status: string;
  scheduled_for: string;
  completed_at: string | null;
  subject: string;
  body_text: string;
  error: string | null;
  created_at: string;
  updated_at: string;
};

export type FollowUpScheduleResponse = {
  success: boolean;
  cancelled_existing: number;
  tasks_created: number;
  tasks: FollowUpTask[];
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
  template_id: string | null;
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

export type QuoteTemplate = {
  id: string;
  business_id: string;
  name: string;
  description: string;
  template_type: QuoteTemplateType;
  field_schema: Record<string, unknown>;
  default_input: Record<string, unknown>;
  design_settings: Record<string, unknown>;
  terms_settings: Record<string, unknown>;
  active: boolean;
  created_at: string;
  updated_at: string;
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
  if (response.status === 204) return undefined as T;
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
  markThreadRead: (businessId: string, threadId: string) =>
    apiFetch<void>(`/businesses/${businessId}/email/threads/${threadId}/mark-read`, {
      method: "POST",
    }),
  markThreadUnread: (businessId: string, threadId: string) =>
    apiFetch<void>(`/businesses/${businessId}/email/threads/${threadId}/mark-unread`, {
      method: "POST",
    }),
  drafts: (businessId: string) =>
    apiFetch<DraftQueueItem[]>(`/businesses/${businessId}/email/drafts`),
  dashboard: (businessId: string, search?: string) => {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    const suffix = params.size ? `?${params.toString()}` : "";
    return apiFetch<DashboardSummary>(`/businesses/${businessId}/dashboard${suffix}`);
  },
  pushStatus: (businessId: string) =>
    apiFetch<PushStatus>(`/businesses/${businessId}/notifications/push`),
  crmLeads: (businessId: string) => apiFetch<CRMLead[]>(`/businesses/${businessId}/crm/leads`),
  crmStats: (businessId: string) => apiFetch<CRMStats>(`/businesses/${businessId}/crm/stats`),
  analytics: (businessId: string, windowDays = 30) =>
    apiFetch<AnalyticsSummary>(
      `/businesses/${businessId}/analytics/summary?window_days=${windowDays}`,
    ),
  marketing: (businessId: string, windowDays = 90) =>
    apiFetch<MarketingSummary>(
      `/businesses/${businessId}/marketing/summary?window_days=${windowDays}`,
    ),
  dailyReportSettings: (businessId: string) =>
    apiFetch<DailyReportSettings>(`/businesses/${businessId}/reports/daily/settings`),
  dailyReportPreview: (businessId: string) =>
    apiFetch<DailyReportPreview>(`/businesses/${businessId}/reports/daily/preview`),
  scheduleFollowUps: (businessId: string, leadId: string, cadence: "standard" | "hot" | "gentle") =>
    apiFetch<FollowUpScheduleResponse>(`/businesses/${businessId}/crm/leads/${leadId}/follow-ups`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cadence }),
    }),
  quotes: (businessId: string) => apiFetch<Quote[]>(`/businesses/${businessId}/quotes`),
  quoteTemplates: (businessId: string) =>
    apiFetch<QuoteTemplate[]>(`/businesses/${businessId}/quotes/templates`),
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


"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import type { BusinessWhatsAppSettings } from "@/lib/api";

const API_URL = "/api/beoos";
const PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type WhatsAppConnectionMode = "coexistence" | "cloud_api_only";

type WhatsAppSignupData = {
  waba_id?: string;
  phone_number_id?: string;
  display_phone_number?: string;
  business_id?: string;
  businessId?: string;
  event?: string;
  version?: number;
};

type SignupAttempt = {
  attempt_id: string;
  state: string;
  app_id: string;
  config_id: string;
  graph_version: string;
  connection_mode: WhatsAppConnectionMode;
  enabled: boolean;
  coexistence_enabled: boolean;
  embedded_signup_version: string;
};

type WhatsAppConnectionTestResult = {
  success: boolean;
  calls_made: string[];
  business_management_checked: boolean;
  whatsapp_business_management_checked: boolean;
  phone_numbers_found: number;
  errors: string[];
};

declare global {
  interface Window {
    FB?: {
      init: (options: Record<string, unknown>) => void;
      login: (
        callback: (response: { authResponse?: { accessToken?: string; code?: string }; status?: string }) => void,
        options: Record<string, unknown>,
      ) => void;
    };
    fbAsyncInit?: () => void;
  }
}

function hasSignupAssets(data: WhatsAppSignupData) {
  return Boolean(data.phone_number_id || data.waba_id || data.business_id || data.businessId);
}

function isTrustedMetaOrigin(value: string) {
  try {
    const url = new URL(value);
    const hostname = url.hostname.toLowerCase();
    return (
      url.protocol === "https:" &&
      (hostname === "facebook.com" ||
        hostname.endsWith(".facebook.com") ||
        hostname === "facebook.net" ||
        hostname.endsWith(".facebook.net"))
    );
  } catch {
    return false;
  }
}

function parsePossiblyNestedMetaData(value: unknown): unknown {
  if (typeof value !== "string") return value;
  try {
    return JSON.parse(value);
  } catch {
    const nested = new URLSearchParams(value).get("data");
    if (!nested) return value;
    try {
      return JSON.parse(nested);
    } catch {
      return value;
    }
  }
}

function parseMetaSignupMessage(raw: unknown): WhatsAppSignupData | null {
  const data = parsePossiblyNestedMetaData(raw);
  if (!data || typeof data !== "object") return null;

  const payload = data as {
    type?: unknown;
    event?: unknown;
    data?: unknown;
    waba_id?: unknown;
    phone_number_id?: unknown;
    display_phone_number?: unknown;
    business_id?: unknown;
    businessId?: unknown;
  };
  if (payload.type && payload.type !== "WA_EMBEDDED_SIGNUP") return null;
  const nestedData = parsePossiblyNestedMetaData(payload.data);
  const source = nestedData && typeof nestedData === "object" ? nestedData : payload;
  const record = source as Record<string, unknown>;
  return {
    waba_id: typeof record.waba_id === "string" ? record.waba_id : undefined,
    phone_number_id: typeof record.phone_number_id === "string" ? record.phone_number_id : undefined,
    display_phone_number: typeof record.display_phone_number === "string" ? record.display_phone_number : undefined,
    business_id: typeof record.business_id === "string" ? record.business_id : undefined,
    businessId: typeof record.businessId === "string" ? record.businessId : undefined,
    event: typeof payload.event === "string" ? payload.event : undefined,
    version: typeof (payload as { version?: unknown }).version === "number"
      ? (payload as { version: number }).version
      : undefined,
  };
}

function formatApiError(error: unknown, fallback: string) {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (typeof error !== "object") return fallback;

  const detail = (error as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (!item || typeof item !== "object") return String(item);
        const field = item as { loc?: unknown; msg?: unknown; message?: unknown };
        const location = Array.isArray(field.loc) ? field.loc.join(".") : "";
        const detailMessage =
          typeof field.msg === "string"
            ? field.msg
            : typeof field.message === "string"
              ? field.message
              : JSON.stringify(item);
        return location ? `${location}: ${detailMessage}` : detailMessage;
      })
      .join("; ");
  }
  if (detail && typeof detail === "object") {
    const field = detail as { message?: unknown; error?: unknown };
    if (typeof field.message === "string") return field.message;
    if (typeof field.error === "string") return field.error;
    return JSON.stringify(detail);
  }
  return fallback;
}

export function WhatsAppSettingsForm({
  businessId,
  settings,
}: {
  businessId: string;
  settings: BusinessWhatsAppSettings;
}) {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  const [testResult, setTestResult] = useState<WhatsAppConnectionTestResult | null>(null);
  const signupDataRef = useRef<WhatsAppSignupData>({});
  const signupWaitersRef = useRef<Array<(data: WhatsAppSignupData) => void>>([]);

  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      const origin = String(event.origin);
      if (!isTrustedMetaOrigin(origin)) return;
      const parsed = parseMetaSignupMessage(event.data);
      console.info("Meta WhatsApp signup message", {
        origin,
        parsed: Boolean(parsed),
        waba_id_present: Boolean(parsed?.waba_id || parsed?.business_id || parsed?.businessId),
        phone_number_id_present: Boolean(parsed?.phone_number_id),
      });
      if (!parsed || !hasSignupAssets(parsed)) return;
      signupDataRef.current = { ...signupDataRef.current, ...parsed };
      signupWaitersRef.current.splice(0).forEach((resolve) => resolve(signupDataRef.current));
    }
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  const waitForSignupAssets = useCallback(() => {
    if (hasSignupAssets(signupDataRef.current)) return Promise.resolve(signupDataRef.current);
    return new Promise<WhatsAppSignupData>((resolve) => {
      const timeout = window.setTimeout(() => {
        signupWaitersRef.current = signupWaitersRef.current.filter((waiter) => waiter !== resolve);
        resolve(signupDataRef.current);
      }, 20000);
      signupWaitersRef.current.push((data) => {
        window.clearTimeout(timeout);
        resolve(data);
      });
    });
  }, []);

  const loadFacebookSdk = useCallback((appId: string, graphVersion: string) => {
    return new Promise<void>((resolve, reject) => {
      if (window.FB) {
        window.FB.init({ appId, autoLogAppEvents: true, cookie: true, xfbml: false, version: graphVersion });
        resolve();
        return;
      }
      window.fbAsyncInit = () => {
        window.FB?.init({ appId, autoLogAppEvents: true, cookie: true, xfbml: false, version: graphVersion });
        resolve();
      };
      if (document.getElementById("facebook-jssdk")) return;
      const script = document.createElement("script");
      script.id = "facebook-jssdk";
      script.async = true;
      script.defer = true;
      script.crossOrigin = "anonymous";
      script.src = "https://connect.facebook.net/en_US/sdk.js";
      script.onerror = () => reject(new Error("Could not load Meta SDK."));
      document.body.appendChild(script);
    });
  }, []);

  async function createSignupAttempt(redirectUri: string, connectionMode: WhatsAppConnectionMode) {
    const response = await fetch(`${API_URL}/businesses/${businessId}/whatsapp/signup-attempt`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ connection_mode: connectionMode, redirect_uri: redirectUri }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => null);
      throw new Error(formatApiError(error, `Meta signup is not configured (${response.status}).`));
    }
    return response.json() as Promise<SignupAttempt>;
  }

  async function connectWithMeta(connectionMode: WhatsAppConnectionMode) {
    setMessage(null);
    setTestResult(null);
    setConnecting(true);
    signupDataRef.current = {};
    try {
      const redirectUri = window.location.href.split("#")[0];
      const attempt = await createSignupAttempt(redirectUri, connectionMode);
      if (!attempt.enabled) throw new Error("Meta WhatsApp signup is not enabled.");
      if (!attempt.app_id || !attempt.config_id) {
        throw new Error(
          `Meta app ID or ${connectionMode === "coexistence" ? "v4 Coexistence" : "standard"} Embedded Signup configuration ID is missing.`,
        );
      }

      await loadFacebookSdk(attempt.app_id, attempt.graph_version || "v25.0");
      window.FB?.login((response) => {
        void (async () => {
          try {
            const code = response.authResponse?.code;
            const accessToken = response.authResponse?.accessToken;
            console.info("Meta WhatsApp login callback", {
              status: response.status,
              code_present: Boolean(code),
              sdk_access_token_present: Boolean(accessToken),
            });
            if (!code && !accessToken) {
              setMessage("Meta signup was cancelled or did not return an authorization code.");
              setConnecting(false);
              return;
            }
            const signupData = await waitForSignupAssets();
            if (!hasSignupAssets(signupData)) {
              throw new Error(
                "Meta returned an authorization code, but did not send WhatsApp session info. Check the Meta configuration, allowed domains, and Embedded Signup sessionInfoVersion.",
              );
            }
            if (
              connectionMode === "coexistence" &&
              signupData.event !== "FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING"
            ) {
              throw new Error(
                "Meta did not complete WhatsApp Business app onboarding. Choose the existing Business app number option and finish verification in WhatsApp.",
              );
            }
            const wabaId = signupData.waba_id ?? signupData.business_id ?? signupData.businessId ?? "";
            const finalizeResponse = await fetch(`${API_URL}/businesses/${businessId}/whatsapp/embedded-signup`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                attempt_id: attempt.attempt_id,
                state: attempt.state,
                connection_mode: attempt.connection_mode,
                code,
                access_token: accessToken ?? "",
                waba_id: wabaId,
                phone_number_id: signupData.phone_number_id ?? "",
                display_phone_number: signupData.display_phone_number ?? "",
                session_event: signupData.event ?? "",
                session_version: signupData.version ?? null,
                redirect_uri: redirectUri,
                meta_payload: signupData,
              }),
            });
            if (!finalizeResponse.ok) {
              const error = await finalizeResponse.json().catch(() => null);
              throw new Error(formatApiError(error, `Meta connection failed (${finalizeResponse.status}).`));
            }
            setMessage(
              connectionMode === "coexistence"
                ? "WhatsApp Business app connected. Contact and history synchronization has started."
                : "WhatsApp connected. You can now run the Meta API test.",
            );
            setConnecting(false);
            router.refresh();
          } catch (error) {
            setMessage(error instanceof Error ? error.message : "Meta connection failed.");
            setConnecting(false);
          }
        })();
      }, {
        config_id: attempt.config_id,
        redirect_uri: redirectUri,
        response_type: "code",
        override_default_response_type: true,
        state: attempt.state,
        extras: {
          setup: {},
          sessionInfoVersion: "3",
        },
      });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Meta connection failed.");
      setConnecting(false);
    }
  }

  async function testConnection() {
    setTestingConnection(true);
    setTestResult(null);
    setMessage(null);
    try {
      const response = await fetch(`${API_URL}/businesses/${businessId}/whatsapp/test-connection`, { method: "POST" });
      const result = await response.json().catch(() => null) as WhatsAppConnectionTestResult | { detail?: string } | null;
      if (!response.ok) {
        const detail = result && "detail" in result ? result.detail : "";
        throw new Error(detail || `Meta API test failed (${response.status}).`);
      }
      const connectionResult = result as WhatsAppConnectionTestResult;
      setTestResult(connectionResult);
      setMessage(connectionResult.success ? "Meta API test completed successfully." : "Meta API test completed with warnings.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Meta API test failed.");
    } finally {
      setTestingConnection(false);
    }
  }

  const hasTenantToken = Boolean(settings.token_configured);
  const statusLabel = settings.connection_status || (settings.enabled ? "connected" : "not connected");
  const modeLabel = settings.connection_mode === "coexistence"
    ? "WhatsApp Business app coexistence"
    : settings.connected_via === "embedded_signup"
      ? "Standard WhatsApp Embedded Signup"
      : "Not connected through Meta signup";

  return (
    <div className="mt-5 rounded-3xl border border-[#eaded4] bg-white p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="max-w-2xl">
          <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#ed633f]">Embedded Signup v4</div>
          <h3 className="mt-2 text-xl font-bold text-[#111827]">Connect WhatsApp with Meta</h3>
          <p className="mt-2 text-sm leading-6 text-[#646a64]">
            Each business authorizes its own WhatsApp Business Account. BeoOS stores the tenant token securely and routes messages by phone number ID.
          </p>
        </div>
        <div className="flex w-full flex-col gap-2 sm:w-auto">
          <Button type="button" onClick={() => connectWithMeta("coexistence")} disabled={connecting} className="w-full sm:min-w-64">
            {connecting ? "Opening Meta..." : "Connect existing Business app"}
          </Button>
          <Button type="button" variant="outline" onClick={() => connectWithMeta("cloud_api_only")} disabled={connecting} className="w-full sm:min-w-64">
            Set up Cloud API only
          </Button>
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatusTile label="Connection" value={statusLabel} detail={modeLabel} />
        <StatusTile
          label="Tenant token"
          value={hasTenantToken ? "Saved" : "Missing"}
          detail={hasTenantToken ? "Ready for Meta API tests." : "Connect with Meta first."}
          tone={hasTenantToken ? "success" : "warning"}
        />
        <StatusTile
          label="Signup"
          value={settings.embedded_signup_version || "v4"}
          detail={settings.connection_mode === "coexistence" ? "Business app + Cloud API" : "Cloud API only"}
        />
        <StatusTile
          label="History sync"
          value={`${settings.history_sync_progress || 0}%`}
          detail={settings.history_sync_status || "not requested"}
          tone={settings.history_sync_status === "completed" ? "success" : "neutral"}
        />
      </div>

      <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-950">
        <p className="font-semibold">Before connecting an existing WhatsApp Business app</p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>Keep the Business app open while Meta synchronizes contacts and up to six months of eligible 1:1 history.</li>
          <li>Complete synchronization within 24 hours or the account must be offboarded and connected again.</li>
          <li>Linked companion devices are disconnected during onboarding and supported devices can be relinked.</li>
          <li>Broadcast lists, groups, disappearing/view-once messages, and some Business app tools are not mirrored to Cloud API.</li>
          <li>Business-app messages remain free; Cloud API messages follow Meta pricing and its separate 24-hour service window.</li>
          <li>Coexistence throughput is limited by Meta to 20 messages per second.</li>
        </ul>
      </div>

      <div className="mt-4 rounded-2xl border border-[#eaded4] bg-[#fffdfa] p-4 text-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-semibold text-[#262a31]">Meta review test</p>
            <p className="mt-1 text-xs text-[#777c76]">Run this after signup to trigger the API calls Meta expects.</p>
          </div>
          <Button type="button" variant="outline" onClick={testConnection} disabled={testingConnection || !hasTenantToken} size="sm">
            {testingConnection ? "Testing..." : "Run Meta API test"}
          </Button>
        </div>

        {testResult && (
          <div className="mt-3 grid gap-2 text-xs text-[#646a64] sm:grid-cols-2">
            <p className="rounded-xl bg-white p-3"><span className="font-semibold text-[#262a31]">Calls:</span> {testResult.calls_made.join(", ") || "none"}</p>
            <p className="rounded-xl bg-white p-3"><span className="font-semibold text-[#262a31]">Phone numbers:</span> {testResult.phone_numbers_found}</p>
            <p className="rounded-xl bg-white p-3"><span className="font-semibold text-[#262a31]">Business:</span> {testResult.business_management_checked ? "passed" : "not confirmed"}</p>
            <p className="rounded-xl bg-white p-3"><span className="font-semibold text-[#262a31]">WhatsApp:</span> {testResult.whatsapp_business_management_checked ? "passed" : "not confirmed"}</p>
            {testResult.errors.length > 0 && <p className="rounded-xl bg-red-50 p-3 text-red-700 sm:col-span-2">{testResult.errors.join(" ")}</p>}
          </div>
        )}
      </div>

      {settings.last_error_message && <p className="mt-4 rounded-xl bg-red-50 p-3 text-xs text-red-700">{settings.last_error_message}</p>}
      {message && <p className="mt-4 rounded-xl bg-[#f7f6f2] p-3 text-xs text-[#747973]">{message}</p>}

      <details className="mt-4 rounded-2xl border border-dashed bg-white p-4 text-xs leading-5 text-[#777c76]">
        <summary className="cursor-pointer font-semibold text-[#262a31]">Webhook callback and review details</summary>
        <code className="mt-2 block break-all rounded-lg bg-[#f7f6f2] p-3 text-[#262a31]">
          {PUBLIC_API_URL.replace(/\/api\/v1$/, "")}/api/v1/webhooks/whatsapp
        </code>
        <p className="mt-2">
          Use this callback in Meta Webhooks with the verify token stored in Railway. Inbound messages route to the correct BeoOS business by phone number ID.
        </p>
        <p className="mt-2">
          Subscribe the Meta app to messages, history, smb_app_state_sync, smb_message_echoes, and account_update.
        </p>
      </details>
    </div>
  );
}

function StatusTile({
  label,
  value,
  detail,
  tone = "neutral",
}: {
  label: string;
  value: string;
  detail: string;
  tone?: "neutral" | "success" | "warning";
}) {
  const valueClass =
    tone === "success" ? "text-emerald-700" : tone === "warning" ? "text-amber-700" : "text-[#262a31]";

  return (
    <div className="rounded-2xl bg-[#f7f6f2] p-4">
      <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#8b8178]">{label}</p>
      <p className={`mt-1 text-sm font-semibold ${valueClass}`}>{value}</p>
      <p className="mt-1 text-xs leading-5 text-[#777c76]">{detail}</p>
    </div>
  );
}

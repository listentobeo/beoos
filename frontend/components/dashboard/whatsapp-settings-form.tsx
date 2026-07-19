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

function parseMetaSignupMessage(raw: unknown): WhatsAppSignupData | null {
  let data = raw;
  if (typeof data === "string") {
    const text = data;
    try {
      data = JSON.parse(text);
    } catch {
      const nested = new URLSearchParams(text).get("data");
      if (!nested) return null;
      try {
        data = JSON.parse(nested);
      } catch {
        return null;
      }
    }
  }
  if (!data || typeof data !== "object") return null;

  const payload = data as {
    type?: unknown;
    data?: unknown;
    waba_id?: unknown;
    phone_number_id?: unknown;
    display_phone_number?: unknown;
    business_id?: unknown;
    businessId?: unknown;
  };
  if (payload.type && payload.type !== "WA_EMBEDDED_SIGNUP") return null;
  const source = payload.data && typeof payload.data === "object" ? payload.data : payload;
  const record = source as Record<string, unknown>;
  return {
    waba_id: typeof record.waba_id === "string" ? record.waba_id : undefined,
    phone_number_id: typeof record.phone_number_id === "string" ? record.phone_number_id : undefined,
    display_phone_number: typeof record.display_phone_number === "string" ? record.display_phone_number : undefined,
    business_id: typeof record.business_id === "string" ? record.business_id : undefined,
    businessId: typeof record.businessId === "string" ? record.businessId : undefined,
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
        const message =
          typeof field.msg === "string"
            ? field.msg
            : typeof field.message === "string"
              ? field.message
              : JSON.stringify(item);
        return location ? `${location}: ${message}` : message;
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
      if (!origin.endsWith("facebook.com") && !origin.endsWith("facebook.net")) return;
      const parsed = parseMetaSignupMessage(event.data);
      if (process.env.NODE_ENV !== "production") {
        console.info("Meta WhatsApp signup message", {
          origin,
          parsed: Boolean(parsed),
          waba_id_present: Boolean(parsed?.waba_id || parsed?.business_id || parsed?.businessId),
          phone_number_id_present: Boolean(parsed?.phone_number_id),
        });
      }
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
      }, 5000);
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

  async function createSignupAttempt(redirectUri: string) {
    const response = await fetch(`${API_URL}/businesses/${businessId}/whatsapp/signup-attempt`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ connection_mode: "coexistence", redirect_uri: redirectUri }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => null);
      throw new Error(formatApiError(error, `Meta signup is not configured (${response.status}).`));
    }
    return response.json() as Promise<SignupAttempt>;
  }

  async function connectWithMeta() {
    setMessage(null);
    setTestResult(null);
    setConnecting(true);
    signupDataRef.current = {};
    try {
      const redirectUri = window.location.href.split("#")[0];
      const attempt = await createSignupAttempt(redirectUri);
      if (!attempt.enabled) throw new Error("Meta WhatsApp signup is not enabled.");
      if (!attempt.coexistence_enabled) throw new Error("WhatsApp coexistence is not enabled on the backend.");
      if (!attempt.app_id || !attempt.config_id) throw new Error("Meta app ID or coexistence configuration ID is missing on Railway.");

      await loadFacebookSdk(attempt.app_id, attempt.graph_version || "v20.0");
      window.FB?.login((response) => {
        void (async () => {
          try {
            const code = response.authResponse?.code;
            const accessToken = response.authResponse?.accessToken;
            if (process.env.NODE_ENV !== "production") {
              console.info("Meta WhatsApp login callback", {
                status: response.status,
                code_present: Boolean(code),
                sdk_access_token_present: Boolean(accessToken),
              });
            }
            if (!code && !accessToken) {
              setMessage("Meta signup was cancelled or did not return an authorization code.");
              setConnecting(false);
              return;
            }
            const signupData = await waitForSignupAssets();
            const wabaId = signupData.waba_id ?? signupData.business_id ?? signupData.businessId ?? "";
            const finalizeResponse = await fetch(`${API_URL}/businesses/${businessId}/whatsapp/embedded-signup`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                attempt_id: attempt.attempt_id,
                state: attempt.state,
                connection_mode: "coexistence",
                code,
                access_token: accessToken ?? "",
                waba_id: wabaId,
                phone_number_id: signupData.phone_number_id ?? "",
                display_phone_number: signupData.display_phone_number ?? "",
                redirect_uri: redirectUri,
                meta_payload: signupData,
              }),
            });
            if (!finalizeResponse.ok) {
              const error = await finalizeResponse.json().catch(() => null);
              throw new Error(formatApiError(error, `Meta connection failed (${finalizeResponse.status}).`));
            }
            setMessage("WhatsApp connected. You can now run the Meta API test.");
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
          featureType: "whatsapp_business_app_onboarding",
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
      ? "Meta tenant signup"
      : "Not connected through Meta signup";

  return (
    <div className="mt-5 grid gap-4">
      <div className="rounded-3xl border border-[#ed633f]/25 bg-gradient-to-br from-[#fff8f5] to-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-2xl">
            <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#ed633f]">Tenant-based WhatsApp setup</div>
            <h3 className="mt-2 text-xl font-bold text-[#111827]">Connect WhatsApp through Meta</h3>
            <p className="mt-2 text-sm leading-6 text-[#646a64]">
              Each business authorizes its own WhatsApp Business Account. BeoOS stores an encrypted tenant token, routes messages to the correct business, and can make the API calls Meta requires for review.
            </p>
          </div>
          <Button type="button" onClick={connectWithMeta} disabled={connecting} className="min-w-48">
            {connecting ? "Opening Meta..." : hasTenantToken ? "Reconnect WhatsApp" : "Connect WhatsApp"}
          </Button>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-3">
          <SetupStep title="1. Meta login" text="Choose the business portfolio, WhatsApp Business Account, and phone number inside Meta." />
          <SetupStep title="2. Tenant token" text="BeoOS encrypts and stores the access token for this business only. No manual shared token is needed." />
          <SetupStep title="3. API review test" text="Run the test to trigger public profile, business management, and WhatsApp management API calls." />
        </div>
      </div>

      <div className="rounded-2xl border bg-white p-4 text-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="font-semibold">Current WhatsApp connection</h3>
            <p className="mt-1 text-[#777c76]">
              {modeLabel} · {statusLabel} · {hasTenantToken ? "tenant token saved" : "tenant token missing"}
            </p>
          </div>
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${hasTenantToken ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
            {hasTenantToken ? "Ready for API test" : "Connect first"}
          </span>
        </div>

        {!hasTenantToken && (
          <p className="mt-3 rounded-xl bg-amber-50 p-3 text-xs leading-5 text-amber-800">
            Old manual WhatsApp IDs may still exist, but Meta API testing needs a tenant access token. Complete the Meta signup above before running the test.
          </p>
        )}
        {settings.last_error_message && <p className="mt-3 rounded-xl bg-red-50 p-3 text-xs text-red-700">{settings.last_error_message}</p>}

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button type="button" variant="outline" onClick={testConnection} disabled={testingConnection || !hasTenantToken} size="sm">
            {testingConnection ? "Testing..." : "Run Meta API test"}
          </Button>
          <p className="text-xs text-[#777c76]">Use this after connection to trigger Meta app review test calls.</p>
        </div>

        {testResult && (
          <div className="mt-3 rounded-xl bg-[#f7f6f2] p-3 text-xs leading-5 text-[#646a64]">
            <p className="font-semibold text-[#262a31]">Calls made: {testResult.calls_made.join(", ") || "none"}</p>
            <p>Business management: {testResult.business_management_checked ? "passed" : "not confirmed"}</p>
            <p>WhatsApp management: {testResult.whatsapp_business_management_checked ? "passed" : "not confirmed"}</p>
            <p>Phone numbers found: {testResult.phone_numbers_found}</p>
            {testResult.errors.length > 0 && <p className="mt-1 text-red-700">{testResult.errors.join(" ")}</p>}
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-dashed bg-white p-4 text-xs leading-5 text-[#777c76]">
        <p className="font-semibold text-[#262a31]">Meta webhook callback</p>
        <code className="mt-2 block break-all rounded-lg bg-[#f7f6f2] p-3 text-[#262a31]">
          {PUBLIC_API_URL.replace(/\/api\/v1$/, "")}/api/v1/webhooks/whatsapp
        </code>
        <p className="mt-2">
          Use this callback in Meta Webhooks with the same verify token stored in Railway. Once a tenant finishes Meta signup, inbound messages are routed by phone number ID to the correct BeoOS business.
        </p>
      </div>

      {message && <p className="rounded-xl bg-[#f7f6f2] p-3 text-xs text-[#747973]">{message}</p>}
    </div>
  );
}

function SetupStep({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-2xl bg-white p-4 text-sm shadow-sm">
      <p className="font-semibold text-[#111827]">{title}</p>
      <p className="mt-1 text-xs leading-5 text-[#777c76]">{text}</p>
    </div>
  );
}

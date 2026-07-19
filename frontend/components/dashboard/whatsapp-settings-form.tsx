"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import type { BusinessWhatsAppSettings } from "@/lib/api";

const inputClass = "w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[#ed633f]/25";
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
      const params = new URLSearchParams(text);
      const nested = params.get("data");
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
    event?: unknown;
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

  try {
    return JSON.stringify(error);
  } catch {
    return fallback;
  }
}

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

export function WhatsAppSettingsForm({
  businessId,
  settings,
}: {
  businessId: string;
  settings: BusinessWhatsAppSettings;
}) {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [connectingMode, setConnectingMode] = useState<WhatsAppConnectionMode | null>(null);
  const [testingConnection, setTestingConnection] = useState(false);
  const [testResult, setTestResult] = useState<WhatsAppConnectionTestResult | null>(null);
  const signupDataRef = useRef<WhatsAppSignupData>({});
  const signupWaitersRef = useRef<Array<(data: WhatsAppSignupData) => void>>([]);

  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      const origin = String(event.origin);
      if (!origin.endsWith("facebook.com") && !origin.endsWith("facebook.net")) return;
      const parsed = parseMetaSignupMessage(event.data);
      if (parsed && hasSignupAssets(parsed)) {
        signupDataRef.current = { ...signupDataRef.current, ...parsed };
        signupWaitersRef.current.splice(0).forEach((resolve) => resolve(signupDataRef.current));
      }
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
        window.FB.init({
          appId,
          autoLogAppEvents: true,
          cookie: true,
          xfbml: false,
          version: graphVersion,
        });
        resolve();
        return;
      }
      window.fbAsyncInit = () => {
        window.FB?.init({
          appId,
          autoLogAppEvents: true,
          cookie: true,
          xfbml: false,
          version: graphVersion,
        });
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

  async function createSignupAttempt(mode: WhatsAppConnectionMode, redirectUri: string) {
    const response = await fetch(`${API_URL}/businesses/${businessId}/whatsapp/signup-attempt`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ connection_mode: mode, redirect_uri: redirectUri }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => null);
      throw new Error(formatApiError(error, `Meta signup is not configured (${response.status}).`));
    }
    return response.json() as Promise<SignupAttempt>;
  }

  async function connectWithMeta(mode: WhatsAppConnectionMode) {
    setMessage(null);
    setConnectingMode(mode);
    signupDataRef.current = {};
    try {
      const redirectUri = window.location.href.split("#")[0];
      const attempt = await createSignupAttempt(mode, redirectUri);
      if (!attempt.enabled) throw new Error("Meta WhatsApp signup is not enabled for this connection mode.");
      if (!attempt.app_id || !attempt.config_id) throw new Error("Meta app ID or WhatsApp configuration ID is missing on Railway.");

      await loadFacebookSdk(attempt.app_id, attempt.graph_version || "v20.0");
      window.FB?.login((response) => {
        void (async () => {
          try {
            const code = response.authResponse?.code;
            const accessToken = response.authResponse?.accessToken;
            if (!code && !accessToken) {
              setMessage("Meta signup was cancelled or did not return an access token.");
              setConnectingMode(null);
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
                connection_mode: attempt.connection_mode,
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
            const label = mode === "coexistence" ? "WhatsApp Business app coexistence" : "dedicated Cloud API number";
            setMessage(`WhatsApp connected through ${label}.`);
            setConnectingMode(null);
            router.refresh();
          } catch (error) {
            setMessage(error instanceof Error ? error.message : "Meta connection failed.");
            setConnectingMode(null);
          }
        })();
      }, {
        config_id: attempt.config_id,
        redirect_uri: redirectUri,
        state: attempt.state,
        extras: {
          setup: {},
          featureType: mode === "coexistence" ? "whatsapp_business_app_onboarding" : undefined,
          sessionInfoVersion: "3",
        },
      });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Meta connection failed.");
      setConnectingMode(null);
    }
  }

  async function save(formData: FormData) {
    setSaving(true);
    setMessage(null);
    const payload: BusinessWhatsAppSettings = {
      enabled: formData.get("enabled") === "on",
      phone_number_id: String(formData.get("phone_number_id") ?? "").trim(),
      business_account_id: String(formData.get("business_account_id") ?? "").trim(),
      display_phone_number: String(formData.get("display_phone_number") ?? "").trim(),
      connected_via: settings.connected_via,
      connection_mode: settings.connection_mode,
      connection_status: settings.connection_status,
      connected_at: settings.connected_at,
      last_error_code: settings.last_error_code,
      last_error_message: settings.last_error_message,
      token_configured: settings.token_configured,
    };
    try {
      const response = await fetch(`${API_URL}/businesses/${businessId}/whatsapp`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(`Save failed (${response.status}).`);
      setMessage("WhatsApp settings saved.");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }


  async function testConnection() {
    setTestingConnection(true);
    setTestResult(null);
    setMessage(null);
    try {
      const response = await fetch(`${API_URL}/businesses/${businessId}/whatsapp/test-connection`, {
        method: "POST",
      });
      const result = await response.json().catch(() => null) as
        | WhatsAppConnectionTestResult
        | { detail?: string }
        | null;
      if (!response.ok) {
        const detail = result && "detail" in result ? result.detail : "";
        throw new Error(detail || `Meta API test failed (${response.status}).`);
      }
      const connectionResult = result as WhatsAppConnectionTestResult;
      setTestResult(connectionResult);
      setMessage(
        connectionResult.success
          ? "Meta API test completed successfully."
          : "Meta API test completed with warnings.",
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Meta API test failed.");
    } finally {
      setTestingConnection(false);
    }
  }
  const statusLabel = settings.connection_status || (settings.enabled ? "connected" : "not connected");
  const modeLabel = settings.connection_mode === "coexistence"
    ? "WhatsApp Business app coexistence"
    : settings.connection_mode === "cloud_api_only"
      ? "Dedicated Cloud API number"
      : settings.connected_via === "embedded_signup"
        ? "Embedded Signup legacy connection"
        : "Manual setup";

  return (
    <div className="mt-5 grid gap-4">
      <div className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-2xl border border-[#ed633f]/25 bg-[#fff8f5] p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#ed633f]">Recommended</div>
              <h3 className="mt-1 font-semibold">Keep WhatsApp on my phone</h3>
              <p className="mt-1 text-sm text-[#777c76]">
                Connect the number already used in WhatsApp Business. Keep using calls, Status, and manual replies while BeoOS receives messages and prepares AI drafts.
              </p>
            </div>
            <Button type="button" onClick={() => connectWithMeta("coexistence")} disabled={Boolean(connectingMode)} size="sm">
              {connectingMode === "coexistence" ? "Connecting..." : "Connect coexistence"}
            </Button>
          </div>
          <ul className="mt-4 grid gap-2 text-xs text-[#777c76]">
            <li>• Number must be active in the official WhatsApp Business app.</li>
            <li>• You need admin access to the Meta business portfolio.</li>
            <li>• Do not delete WhatsApp or deregister the number.</li>
          </ul>
        </div>

        <div className="rounded-2xl border bg-white p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h3 className="font-semibold">Use a dedicated API number</h3>
              <p className="mt-1 text-sm text-[#777c76]">
                Connect a separate number managed by BeoOS and WhatsApp Cloud API. Use this when the business does not need the same number on the phone app.
              </p>
            </div>
            <Button type="button" variant="outline" onClick={() => connectWithMeta("cloud_api_only")} disabled={Boolean(connectingMode)} size="sm">
              {connectingMode === "cloud_api_only" ? "Connecting..." : "Connect API number"}
            </Button>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border bg-white p-4 text-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="font-semibold">Current WhatsApp connection</h3>
            <p className="mt-1 text-[#777c76]">{modeLabel} · {statusLabel}{settings.token_configured ? " · tenant token saved" : ""}</p>
          </div>
          {settings.last_error_message && <span className="rounded-full bg-red-50 px-3 py-1 text-xs font-semibold text-red-700">Needs attention</span>}
        </div>
        {settings.last_error_message && <p className="mt-3 rounded-xl bg-red-50 p-3 text-xs text-red-700">{settings.last_error_message}</p>}
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button type="button" variant="outline" onClick={testConnection} disabled={testingConnection} size="sm">
            {testingConnection ? "Testing..." : "Run Meta API test"}
          </Button>
          <p className="text-xs text-[#777c76]">
            Use this after connection to trigger Meta app review test calls.
          </p>
        </div>
        {testResult && (
          <div className="mt-3 rounded-xl bg-[#f7f6f2] p-3 text-xs leading-5 text-[#646a64]">
            <p className="font-semibold text-[#262a31]">
              Calls made: {testResult.calls_made.join(", ") || "none"}
            </p>
            <p>Business management: {testResult.business_management_checked ? "passed" : "not confirmed"}</p>
            <p>WhatsApp management: {testResult.whatsapp_business_management_checked ? "passed" : "not confirmed"}</p>
            <p>Phone numbers found: {testResult.phone_numbers_found}</p>
            {testResult.errors.length > 0 && (
              <p className="mt-1 text-red-700">{testResult.errors.join(" ")}</p>
            )}
          </div>
        )}
      </div>

      <form action={save} className="grid gap-3">
        <label className="flex items-start gap-3 rounded-xl bg-[#f7f6f2] p-3 text-sm">
          <input name="enabled" type="checkbox" defaultChecked={settings.enabled} className="mt-1" />
          <span>
            <span className="block font-semibold">Enable WhatsApp Cloud API for this business</span>
            <span className="text-[#777c76]">Inbound webhooks will create inbox threads for this tenant.</span>
          </span>
        </label>
        <label className="text-xs font-semibold text-[#646a64]">
          Meta phone number ID
          <input className={`${inputClass} mt-1.5`} name="phone_number_id" defaultValue={settings.phone_number_id} placeholder="e.g. 123456789012345" />
        </label>
        <label className="text-xs font-semibold text-[#646a64]">
          WhatsApp Business Account ID
          <input className={`${inputClass} mt-1.5`} name="business_account_id" defaultValue={settings.business_account_id} placeholder="Optional but useful for audits" />
        </label>
        <label className="text-xs font-semibold text-[#646a64]">
          Display phone number
          <input className={`${inputClass} mt-1.5`} name="display_phone_number" defaultValue={settings.display_phone_number} placeholder="+234..." />
        </label>
        <div className="rounded-xl border border-dashed bg-white p-3 text-xs leading-5 text-[#777c76]">
          Webhook callback:
          <code className="mt-1 block break-all rounded-lg bg-[#f7f6f2] p-2 text-[#262a31]">
            {PUBLIC_API_URL.replace(/\/api\/v1$/, "")}/api/v1/webhooks/whatsapp
          </code>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={saving} size="sm">{saving ? "Saving..." : "Save WhatsApp settings"}</Button>
          {message && <p className="text-xs text-[#747973]">{message}</p>}
        </div>
      </form>
    </div>
  );
}


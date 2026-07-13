"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";
import type { BusinessWhatsAppSettings } from "@/lib/api";

const inputClass = "w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[#ed633f]/25";
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const META_APP_ID = process.env.NEXT_PUBLIC_META_APP_ID ?? "";
const META_WHATSAPP_CONFIG_ID = process.env.NEXT_PUBLIC_META_WHATSAPP_CONFIG_ID ?? "";
const META_GRAPH_VERSION = process.env.NEXT_PUBLIC_META_GRAPH_VERSION ?? "v20.0";

type WhatsAppSignupData = {
  waba_id?: string;
  phone_number_id?: string;
  display_phone_number?: string;
  business_id?: string;
};

declare global {
  interface Window {
    FB?: {
      init: (options: Record<string, unknown>) => void;
      login: (
        callback: (response: { authResponse?: { code?: string }; status?: string }) => void,
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
  const { getToken } = useAuth();
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const signupDataRef = useRef<WhatsAppSignupData>({});

  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      if (!String(event.origin).endsWith("facebook.com")) return;
      let data: unknown = event.data;
      if (typeof data === "string") {
        try {
          data = JSON.parse(data);
        } catch {
          return;
        }
      }
      if (!data || typeof data !== "object") return;
      const payload = data as { type?: string; event?: string; data?: WhatsAppSignupData };
      if (payload.type === "WA_EMBEDDED_SIGNUP" && payload.data) {
        signupDataRef.current = payload.data;
      }
    }
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  const loadFacebookSdk = useCallback(() => {
    return new Promise<void>((resolve, reject) => {
      if (window.FB) {
        resolve();
        return;
      }
      window.fbAsyncInit = () => {
        window.FB?.init({
          appId: META_APP_ID,
          autoLogAppEvents: true,
          xfbml: false,
          version: META_GRAPH_VERSION,
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

  async function connectWithMeta() {
    setMessage(null);
    if (!META_APP_ID || !META_WHATSAPP_CONFIG_ID) {
      setMessage("Add NEXT_PUBLIC_META_APP_ID and NEXT_PUBLIC_META_WHATSAPP_CONFIG_ID first.");
      return;
    }
    setConnecting(true);
    signupDataRef.current = {};
    try {
      const token = await getToken();
      const redirectUri = `${window.location.origin}/`;
      const configResponse = await fetch(`${API_URL}/businesses/${businessId}/whatsapp/embedded-config`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!configResponse.ok) throw new Error("Embedded Signup is not configured on the backend.");
      const config = await configResponse.json() as { enabled: boolean; graph_version?: string };
      if (!config.enabled) throw new Error("Add META_APP_ID, META_APP_SECRET, and META_WHATSAPP_CONFIG_ID on Railway.");

      await loadFacebookSdk();
      window.FB?.login((response) => {
        void (async () => {
          try {
          const code = response.authResponse?.code;
          if (!code) {
            setMessage("Meta signup was cancelled or did not return a code.");
            setConnecting(false);
            return;
          }
          const signupData = signupDataRef.current;
          const finalizeResponse = await fetch(`${API_URL}/businesses/${businessId}/whatsapp/embedded-signup`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              code,
              waba_id: signupData.waba_id ?? signupData.business_id ?? "",
              phone_number_id: signupData.phone_number_id ?? "",
              display_phone_number: signupData.display_phone_number ?? "",
              redirect_uri: redirectUri,
              meta_payload: signupData,
            }),
          });
          if (!finalizeResponse.ok) {
            const error = await finalizeResponse.json().catch(() => ({}));
            throw new Error(error.detail ?? `Meta connection failed (${finalizeResponse.status}).`);
          }
          setMessage("WhatsApp connected through Meta Embedded Signup.");
          setConnecting(false);
          router.refresh();
          } catch (error) {
            setMessage(error instanceof Error ? error.message : "Meta connection failed.");
            setConnecting(false);
          }
        })();
      }, {
        config_id: META_WHATSAPP_CONFIG_ID,
        response_type: "code",
        override_default_response_type: true,
        redirect_uri: redirectUri,
        extras: {
          featureType: "whatsapp_business_app_onboarding",
          sessionInfoVersion: "3",
        },
      });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Meta connection failed.");
      setConnecting(false);
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
      connected_at: settings.connected_at,
      token_configured: settings.token_configured,
    };
    try {
      const token = await getToken();
      const response = await fetch(`${API_URL}/businesses/${businessId}/whatsapp`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
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

  return (
    <div className="mt-5 grid gap-4">
      <div className="rounded-2xl border bg-white p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h3 className="font-semibold">Connect customer-owned WhatsApp</h3>
            <p className="mt-1 text-sm text-[#777c76]">
              Recommended for SaaS tenants. The customer logs into Meta and connects their own WABA/phone number to this business only.
            </p>
            <p className="mt-2 text-xs text-[#777c76]">
              Status: {settings.connected_via === "embedded_signup" ? "Connected with Meta Embedded Signup" : "Manual setup"}
              {settings.token_configured ? " · tenant token saved" : ""}
            </p>
          </div>
          <Button type="button" onClick={connectWithMeta} disabled={connecting} size="sm">
            {connecting ? "Connecting..." : "Connect with Meta"}
          </Button>
        </div>
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
          {API_URL.replace(/\/api\/v1$/, "")}/api/v1/webhooks/whatsapp
        </code>
      </div>
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={saving} size="sm">{saving ? "Saving..." : "Save WhatsApp settings"}</Button>
        {message && <p className="text-xs text-[#747973]">{message}</p>}
      </div>
      </form>
    </div>
  );
}

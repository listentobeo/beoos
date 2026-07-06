"use client";

import { BellRing, LoaderCircle } from "lucide-react";
import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";
import type { PushStatus } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

function urlBase64ToUint8Array(value: string) {
  const padding = "=".repeat((4 - (value.length % 4)) % 4);
  const base64 = `${value}${padding}`.replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(base64);
  return Uint8Array.from([...raw].map((character) => character.charCodeAt(0)));
}

function serializeSubscription(subscription: PushSubscription) {
  const json = subscription.toJSON();
  return {
    endpoint: json.endpoint ?? subscription.endpoint,
    keys: {
      p256dh: json.keys?.p256dh ?? "",
      auth: json.keys?.auth ?? "",
    },
    user_agent: window.navigator.userAgent,
  };
}

export function PushNotificationSettings({
  businessId,
  initialStatus,
}: {
  businessId: string;
  initialStatus: PushStatus;
}) {
  const { getToken } = useAuth();
  const [status, setStatus] = useState(initialStatus);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function ensureServiceWorker() {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      throw new Error("This browser does not support push notifications.");
    }
    return navigator.serviceWorker.register("/beoos-sw.js");
  }

  async function enable() {
    setLoading(true);
    setMessage(null);
    try {
      if (!status.vapid_public_key) {
        throw new Error("VAPID public key is not configured on the backend.");
      }
      if (!("Notification" in window)) {
        throw new Error("This browser does not support notifications.");
      }
      const permission = await Notification.requestPermission();
      if (permission !== "granted") throw new Error("Notification permission was not granted.");
      const registration = await ensureServiceWorker();
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(status.vapid_public_key),
      });
      const token = await getToken();
      const response = await fetch(`${API_URL}/businesses/${businessId}/notifications/push`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(serializeSubscription(subscription)),
      });
      if (!response.ok) throw new Error(`Push setup failed (${response.status}).`);
      setStatus((await response.json()) as PushStatus);
      setMessage("Push notifications are enabled for this business on this device.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Push setup failed.");
    } finally {
      setLoading(false);
    }
  }

  async function disable() {
    setLoading(true);
    setMessage(null);
    try {
      const registration = await navigator.serviceWorker.getRegistration("/beoos-sw.js");
      const subscription = await registration?.pushManager.getSubscription();
      if (subscription) {
        const token = await getToken();
        await fetch(`${API_URL}/businesses/${businessId}/notifications/push`, {
          method: "DELETE",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(serializeSubscription(subscription)),
        });
        await subscription.unsubscribe();
      }
      setStatus({ ...status, enabled: false });
      setMessage("Push notifications are disabled on this device.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not disable push notifications.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-5 rounded-2xl border bg-[#fbfaf7] p-4">
      <div className="flex items-start gap-3">
        <div className="grid size-10 place-items-center rounded-xl bg-blue-50 text-blue-700">
          <BellRing className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="font-bold">Browser push notifications</h3>
          <p className="mt-1 text-sm leading-6 text-[#747973]">
            Get notified on this device when new email, website form, or WhatsApp messages enter this business inbox.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            {status.enabled ? (
              <Button type="button" variant="outline" size="sm" onClick={disable} disabled={loading}>
                {loading && <LoaderCircle className="size-4 animate-spin" />}
                Disable on this device
              </Button>
            ) : (
              <Button type="button" size="sm" onClick={enable} disabled={loading}>
                {loading && <LoaderCircle className="size-4 animate-spin" />}
                Enable push notifications
              </Button>
            )}
            <span className="text-xs font-semibold text-[#747973]">
              {status.enabled ? "Enabled" : "Not enabled"}
            </span>
          </div>
          {message && <p className="mt-3 text-xs text-[#747973]">{message}</p>}
        </div>
      </div>
    </div>
  );
}

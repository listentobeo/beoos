self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = {};
  }
  const title = data.title || "New BeoOS message";
  const options = {
    body: data.body || "Open BeoOS to review the new conversation.",
    icon: "/favicon.svg",
    badge: "/favicon.svg",
    tag: data.tag || "beoos-inbox",
    renotify: true,
    silent: false,
    requireInteraction: false,
    timestamp: Date.now(),
    data: {
      url: data.url || "/dashboard/inbox",
    },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url || "/dashboard/inbox";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ("focus" in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      return self.clients.openWindow(url);
    }),
  );
});

self.addEventListener("message", (event) => {
  if (event.data?.type !== "BEOOS_SHOW_TEST_NOTIFICATION") return;
  event.waitUntil(
    self.registration.showNotification("BeoOS browser test", {
      body: "If you can see this, browser notifications are allowed on this device.",
      icon: "/favicon.svg",
      badge: "/favicon.svg",
      tag: "beoos-local-test",
      renotify: true,
      silent: false,
      requireInteraction: false,
      data: { url: "/dashboard/settings#notifications" },
    }),
  );
});

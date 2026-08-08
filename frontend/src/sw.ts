/// <reference lib="webworker" />
import { cleanupOutdatedCaches, precacheAndRoute } from "workbox-precaching";

declare const self: ServiceWorkerGlobalScope;

// Injected at build time by vite-plugin-pwa (injectManifest strategy).
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

/** Take over immediately. A stale worker would keep serving an old push
 * handler, and push delivery is the one thing this product cannot get
 * wrong. */
self.addEventListener("install", () => {
  void self.skipWaiting();
});
self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

interface PushPayload {
  title: string;
  body: string;
  url: string;
}

/** The backend sends {title, body, url}. Anything unparseable still shows a
 * notification: iOS revokes push permission from workers that receive a
 * push and display nothing. */
function readPayload(event: PushEvent): PushPayload {
  const fallback: PushPayload = {
    title: "Aimentum",
    body: "Open Aimentum to see what is next.",
    url: "/",
  };
  if (!event.data) return fallback;
  try {
    const parsed = event.data.json() as Partial<PushPayload>;
    return {
      title: typeof parsed.title === "string" ? parsed.title : fallback.title,
      body: typeof parsed.body === "string" ? parsed.body : fallback.body,
      url: typeof parsed.url === "string" ? parsed.url : fallback.url,
    };
  } catch {
    return fallback;
  }
}

self.addEventListener("push", (event) => {
  const payload = readPayload(event);
  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: "/icons/icon-192.png",
      badge: "/icons/badge.png",
      // One accountability agent, one conversation: a new nudge replaces the
      // last one rather than stacking up a wall of unread reminders.
      tag: "aimentum",
      renotify: true,
      data: { url: payload.url },
    } as NotificationOptions),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data as { url?: string } | undefined)?.url ?? "/";
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({
        type: "window",
        includeUncontrolled: true,
      });
      // Focus an open tab instead of opening a second copy of the app.
      const existing = windows.find((client) => client.url.includes(self.location.origin));
      if (existing) {
        await existing.focus();
        if ("navigate" in existing) await existing.navigate(target);
        return;
      }
      await self.clients.openWindow(target);
    })(),
  );
});

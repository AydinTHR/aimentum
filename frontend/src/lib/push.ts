import { api } from "../api/client";

/** VAPID keys travel as base64url; PushManager wants raw bytes. */
function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
  const normalized = padded.replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(normalized);
  return Uint8Array.from(raw, (char) => char.charCodeAt(0));
}

export interface PushState {
  supported: boolean;
  permission: NotificationPermission | "unsupported";
  subscribed: boolean;
}

export function pushSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

export async function readPushState(): Promise<PushState> {
  if (!pushSupported()) {
    return { supported: false, permission: "unsupported", subscribed: false };
  }
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();
  return {
    supported: true,
    permission: Notification.permission,
    subscribed: subscription !== null,
  };
}

/** Ask for permission, subscribe with the server's key, and register the
 * result with the API. Priority zero of this product is that notifications
 * actually arrive, so every failure here is surfaced, never swallowed. */
export async function enablePush(): Promise<void> {
  if (!pushSupported()) {
    throw new Error("This browser cannot receive push notifications.");
  }
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error(
      "Notifications are blocked. Allow them in your browser settings, then try again.",
    );
  }

  const { public_key: publicKey } = await api.vapidPublicKey();
  if (!publicKey) {
    throw new Error("The server has no VAPID public key configured.");
  }

  const registration = await navigator.serviceWorker.ready;
  const existing = await registration.pushManager.getSubscription();
  const subscription =
    existing ??
    (await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey) as BufferSource,
    }));

  const json = subscription.toJSON();
  if (!json.keys?.p256dh || !json.keys.auth || !json.endpoint) {
    throw new Error("The browser returned an incomplete subscription.");
  }
  await api.pushSubscribe({
    endpoint: json.endpoint,
    keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
    user_agent: navigator.userAgent.slice(0, 500),
  });
}

/** Unsubscribe locally first, then tell the API. If the local unsubscribe
 * fails there is nothing to deregister, and if the API call fails the next
 * send prunes the endpoint anyway. */
export async function disablePush(): Promise<void> {
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();
  if (!subscription) return;
  const endpoint = subscription.endpoint;
  await subscription.unsubscribe();
  try {
    await api.pushUnsubscribe(endpoint);
  } catch {
    // A 404 means the server already forgot it, which is the goal anyway.
  }
}

/** iOS only delivers web push to apps installed to the home screen, so the
 * Settings screen has to say so rather than let the toggle fail silently. */
export function isIosSafariNotInstalled(): boolean {
  if (typeof navigator === "undefined") return false;
  // An iPad reports itself as a Mac, so the touch-point check is the only way
  // to spot one. Android is excluded explicitly: it reports touch points too,
  // and a device emulator can pair an Android agent with a desktop platform,
  // which would show iPhone instructions to someone who has no share sheet.
  if (/android/i.test(navigator.userAgent)) return false;
  const isIos =
    /iphone|ipad|ipod/i.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  if (!isIos) return false;
  const standalone =
    window.matchMedia("(display-mode: standalone)").matches ||
    ("standalone" in navigator && (navigator as { standalone?: boolean }).standalone === true);
  return !standalone;
}

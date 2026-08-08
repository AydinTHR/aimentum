import { useState } from "react";

import { isIosSafariNotInstalled } from "../lib/push";
import { ShareIcon } from "./icons";

const DISMISSED_KEY = "aimentum.installHintDismissed";

/** iOS does not deliver web push to a browser tab, only to an app installed
 * on the home screen. Without this the notification toggle in Settings would
 * simply fail on the one device the owner actually carries. */
export function InstallHint() {
  const [dismissed, setDismissed] = useState(() => localStorage.getItem(DISMISSED_KEY) === "1");
  if (dismissed || !isIosSafariNotInstalled()) return null;

  return (
    <div className="mb-4 flex items-start gap-3 rounded-2xl border border-emerald-800/50 bg-emerald-950/30 p-3.5">
      <ShareIcon className="mt-0.5 size-5 shrink-0 text-emerald-400" />
      <div className="min-w-0 flex-1">
        <p className="text-sm text-zinc-200">
          Add Aimentum to your home screen to get notifications. Tap the share button below, then
          Add to Home Screen.
        </p>
        <button
          onClick={() => {
            localStorage.setItem(DISMISSED_KEY, "1");
            setDismissed(true);
          }}
          className="mt-2 text-xs text-zinc-400 hover:text-zinc-200"
        >
          Not now
        </button>
      </div>
    </div>
  );
}

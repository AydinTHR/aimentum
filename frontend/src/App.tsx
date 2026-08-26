import { useState, useSyncExternalStore } from "react";

import { tokenStore } from "./api/client";
import { BookIcon, GearIcon, SunIcon, TargetIcon } from "./components/icons";
import { InstallHint } from "./components/InstallHint";
import { GoalsScreen } from "./screens/Goals";
import { RetrosScreen } from "./screens/Retros";
import { SettingsScreen } from "./screens/Settings";
import { TodayScreen } from "./screens/Today";
import { TokenGate } from "./TokenGate";

const TABS = [
  { id: "today", label: "Today", Icon: SunIcon },
  { id: "goals", label: "Goals", Icon: TargetIcon },
  { id: "retros", label: "Retros", Icon: BookIcon },
  { id: "settings", label: "Settings", Icon: GearIcon },
] as const;

type TabId = (typeof TABS)[number]["id"];

/** The tab the app opens on, taken from the path.
 *
 * Notifications carry a url: /today for the daily jobs, /retros for the
 * Sunday one, and the service worker navigates to it. Without this the app
 * always opened on Today, so tapping the retro notification landed a tap
 * away from the thing it was announcing. Anything unrecognised falls back to
 * Today rather than showing nothing.
 */
function tabFromPath(pathname: string): TabId {
  const candidate = pathname.replace(/^\/+|\/+$/g, "");
  return TABS.find((entry) => entry.id === candidate)?.id ?? "today";
}

function App() {
  const token = useSyncExternalStore(tokenStore.subscribe, tokenStore.get);
  const [tab, setTab] = useState<TabId>(() => tabFromPath(window.location.pathname));

  if (!token) return <TokenGate />;

  return (
    <div className="mx-auto flex min-h-svh w-full max-w-md flex-col">
      <main className="flex-1 px-4 pb-28 pt-6">
        <InstallHint />
        {tab === "today" && <TodayScreen />}
        {tab === "goals" && <GoalsScreen />}
        {tab === "retros" && <RetrosScreen />}
        {tab === "settings" && <SettingsScreen />}
      </main>
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 border-t border-zinc-800 bg-zinc-950/85 pb-[env(safe-area-inset-bottom)] backdrop-blur"
      >
        <div className="mx-auto grid max-w-md grid-cols-4">
          {TABS.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => {
                setTab(id);
                // Keep the address honest, so a reload or a notification
                // arriving at an open window resumes where the owner is.
                window.history.replaceState(null, "", `/${id}`);
              }}
              aria-current={tab === id ? "page" : undefined}
              className={`flex flex-col items-center gap-1 py-2.5 text-[11px] font-medium transition-colors ${
                tab === id ? "text-emerald-400" : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              <Icon className="size-5" />
              {label}
            </button>
          ))}
        </div>
      </nav>
    </div>
  );
}

export default App;

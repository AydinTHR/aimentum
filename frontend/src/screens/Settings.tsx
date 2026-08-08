import { useEffect, useState } from "react";

import { api, tokenStore } from "../api/client";
import type { PushTestResult, Settings } from "../api/types";
import { BellIcon } from "../components/icons";
import { Button, Card, ErrorNote, SectionLabel, Spinner } from "../components/ui";
import {
  disablePush,
  enablePush,
  isIosSafariNotInstalled,
  readPushState,
  type PushState,
} from "../lib/push";
import { useApi } from "../lib/useApi";

export function SettingsScreen() {
  const settings = useApi(api.settings);

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-50">Settings</h1>
      </header>

      <NotificationsCard />

      {settings.loading && !settings.data && <Spinner label="Loading settings" />}
      {settings.error && !settings.data && <ErrorNote>{settings.error}</ErrorNote>}
      {settings.data && <PreferencesCard settings={settings.data} />}

      <Card>
        <SectionLabel>Access</SectionLabel>
        <p className="mt-2 text-sm text-zinc-400">
          Signing out clears the token on this device. Notifications stop until you sign back in and
          enable them again.
        </p>
        <Button
          variant="danger"
          className="mt-3 w-full"
          onClick={() => {
            void disablePush().finally(() => tokenStore.clear());
          }}
        >
          Sign out
        </Button>
      </Card>
    </div>
  );
}

function NotificationsCard() {
  const [state, setState] = useState<PushState>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [testResult, setTestResult] = useState<PushTestResult>();
  const needsInstall = isIosSafariNotInstalled();

  useEffect(() => {
    void readPushState().then(setState);
  }, []);

  async function toggle() {
    if (busy) return;
    setBusy(true);
    setError(undefined);
    setTestResult(undefined);
    try {
      if (state?.subscribed) {
        await disablePush();
      } else {
        await enablePush();
      }
      setState(await readPushState());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function sendTest() {
    if (busy) return;
    setBusy(true);
    setError(undefined);
    setTestResult(undefined);
    try {
      setTestResult(await api.pushTest());
      setState(await readPushState());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send the test.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <div className="flex items-center gap-2">
        <BellIcon className="size-4 text-zinc-400" />
        <SectionLabel>Notifications</SectionLabel>
      </div>

      {needsInstall && (
        <p className="mt-3 rounded-lg border border-zinc-700 bg-zinc-800/40 px-3 py-2 text-sm text-zinc-300">
          On iPhone, notifications only work once Aimentum is installed to your home screen. Tap the
          share button in Safari, then Add to Home Screen, and open it from there.
        </p>
      )}

      {state === undefined ? (
        <div className="mt-3">
          <Spinner label="Checking this device" />
        </div>
      ) : !state.supported ? (
        <p className="mt-3 text-sm text-zinc-400">
          This browser cannot receive push notifications.
        </p>
      ) : (
        <>
          <p className="mt-3 text-sm text-zinc-400">
            {state.subscribed
              ? "This device is registered. Aimentum will reach you here."
              : "This device is not registered yet, so nothing will reach you."}
          </p>
          <div className="mt-3 flex gap-2">
            <Button
              onClick={() => void toggle()}
              disabled={busy}
              variant={state.subscribed ? "ghost" : "primary"}
              className="flex-1"
            >
              {busy ? "Working..." : state.subscribed ? "Turn off here" : "Turn on here"}
            </Button>
            {state.subscribed && (
              <Button onClick={() => void sendTest()} disabled={busy} variant="ghost">
                Send test
              </Button>
            )}
          </div>
        </>
      )}

      {testResult && (
        <p className="mt-3 text-sm text-zinc-300">
          {testResult.sent === 0
            ? "No registered devices to send to."
            : `Sent to ${testResult.sent} device${testResult.sent === 1 ? "" : "s"}: ${testResult.statuses.join(", ")}.`}
          {testResult.pruned > 0 &&
            ` ${testResult.pruned} dead subscription${
              testResult.pruned === 1 ? " was" : "s were"
            } removed.`}
        </p>
      )}
      {error && <div className="mt-3">{<ErrorNote>{error}</ErrorNote>}</div>}
    </Card>
  );
}

function PreferencesCard({ settings }: { settings: Settings }) {
  const [current, setCurrent] = useState(settings);
  const [error, setError] = useState<string>();
  const [saving, setSaving] = useState(false);

  async function patch(change: Partial<Settings>) {
    const previous = current;
    setCurrent({ ...current, ...change });
    setSaving(true);
    setError(undefined);
    try {
      setCurrent(await api.patchSettings(change));
    } catch (err) {
      setCurrent(previous);
      setError(err instanceof Error ? err.message : "Could not save.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <SectionLabel>
        Preferences{saving && <span className="ml-2 text-zinc-600">saving</span>}
      </SectionLabel>

      <div className="mt-4 flex items-center justify-between gap-3">
        <label htmlFor="floor" className="text-sm text-zinc-300">
          Applications per day
          <span className="mt-0.5 block text-xs text-zinc-500">
            The floor the evening check-in measures against.
          </span>
        </label>
        <input
          id="floor"
          type="number"
          min={0}
          value={current.applications_floor}
          onChange={(event) =>
            setCurrent({ ...current, applications_floor: Number(event.target.value) || 0 })
          }
          onBlur={(event) => void patch({ applications_floor: Number(event.target.value) || 0 })}
          className="w-16 rounded-lg border border-zinc-700 bg-zinc-950/60 py-1.5 text-center text-sm tabular-nums text-zinc-100 focus:border-emerald-600 focus:outline-none"
        />
      </div>

      {/* Stacked, not side by side: two time inputs plus a label do not fit
          across a phone, and squeezing them wraps the hint one word per line. */}
      <div className="mt-4">
        <span className="text-sm text-zinc-300">
          Workday
          <span className="mt-0.5 block text-xs text-zinc-500">
            Time blocks stay inside these hours.
          </span>
        </span>
        <div className="mt-2 flex items-center gap-2">
          <input
            type="time"
            aria-label="Workday start"
            value={current.workday_start.slice(0, 5)}
            onChange={(event) => void patch({ workday_start: `${event.target.value}:00` })}
            className="min-w-0 flex-1 rounded-lg border border-zinc-700 bg-zinc-950/60 px-2 py-1.5 text-sm tabular-nums text-zinc-100 focus:border-emerald-600 focus:outline-none"
          />
          <span className="shrink-0 text-xs text-zinc-600">to</span>
          <input
            type="time"
            aria-label="Workday end"
            value={current.workday_end.slice(0, 5)}
            onChange={(event) => void patch({ workday_end: `${event.target.value}:00` })}
            className="min-w-0 flex-1 rounded-lg border border-zinc-700 bg-zinc-950/60 px-2 py-1.5 text-sm tabular-nums text-zinc-100 focus:border-emerald-600 focus:outline-none"
          />
        </div>
      </div>

      <Toggle
        label="Write time blocks to my calendar"
        hint="Blocks land in the Aimentum calendar, around your real meetings."
        checked={current.time_blocking_enabled}
        onChange={(value) => void patch({ time_blocking_enabled: value })}
      />
      <Toggle
        label="Read my plan back to me"
        hint="A short spoken summary after the morning check-in."
        checked={current.read_back_enabled}
        onChange={(value) => void patch({ read_back_enabled: value })}
      />

      {error && <div className="mt-3">{<ErrorNote>{error}</ErrorNote>}</div>}
    </Card>
  );
}

function Toggle({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <div className="mt-4 flex items-center justify-between gap-3">
      <span className="text-sm text-zinc-300">
        {label}
        <span className="mt-0.5 block text-xs text-zinc-500">{hint}</span>
      </span>
      <button
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
          checked ? "bg-emerald-600" : "bg-zinc-700"
        }`}
      >
        <span
          className={`absolute top-0.5 size-5 rounded-full bg-white transition-[left] ${
            checked ? "left-[22px]" : "left-0.5"
          }`}
        />
      </button>
    </div>
  );
}

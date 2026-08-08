import { useState } from "react";

import { tokenStore, verifyToken } from "./api/client";
import { Button, ErrorNote } from "./components/ui";

/** The single lock on the app. There is no signup and no account: one owner,
 * one shared token, checked against the API before letting anyone in. */
export function TokenGate() {
  const [token, setToken] = useState("");
  const [error, setError] = useState<string>();
  const [checking, setChecking] = useState(false);

  async function unlock(event: React.FormEvent) {
    event.preventDefault();
    const candidate = token.trim();
    if (!candidate || checking) return;
    setChecking(true);
    setError(undefined);
    try {
      // Prove the token before storing it: storing it first would render the
      // app and unmount this form before it could report a rejection.
      await verifyToken(candidate);
      tokenStore.set(candidate);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setChecking(false);
    }
  }

  return (
    <main className="flex min-h-svh flex-col items-center justify-center px-6">
      <h1 className="text-3xl font-semibold tracking-tight text-zinc-50">Aimentum</h1>
      <p className="mt-2 max-w-xs text-center text-sm text-zinc-400">
        Your accountability agent. It reaches out to you, not the other way around.
      </p>
      <form onSubmit={unlock} className="mt-8 flex w-full max-w-xs flex-col gap-3">
        <input
          type="password"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          placeholder="Access token"
          autoComplete="current-password"
          aria-label="Access token"
          className="rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-emerald-600 focus:outline-none"
        />
        <Button type="submit" disabled={!token.trim() || checking}>
          {checking ? "Checking" : "Unlock"}
        </Button>
        {error && <ErrorNote>{error}</ErrorNote>}
      </form>
    </main>
  );
}

import { useState } from "react";

import { api } from "../api/client";
import type { EveningResult, Task } from "../api/types";
import { Button, Card, ErrorNote, SectionLabel } from "./ui";

interface Props {
  tasks: Task[];
  onDone: (result: EveningResult) => void;
}

/** Close out the day: applications count, optional note, and the task
 * states as currently checked off. The agent writes the reflection. */
export function EveningForm({ tasks, onDone }: Props) {
  const [applications, setApplications] = useState(0);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>();

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(undefined);
    try {
      const result = await api.eveningCheckin(
        applications,
        note.trim() || null,
        tasks.map((task) => ({ id: task.id, done: task.done })),
      );
      onDone(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <SectionLabel>Evening check-in</SectionLabel>
      <form onSubmit={submit} className="mt-3 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <label htmlFor="applications-sent" className="text-sm text-zinc-300">
            Applications sent today
          </label>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setApplications((n) => Math.max(0, n - 1))}
              aria-label="One fewer application"
              className="flex size-9 items-center justify-center rounded-lg border border-zinc-700 text-lg text-zinc-300 hover:border-zinc-500"
            >
              -
            </button>
            <input
              id="applications-sent"
              type="number"
              min={0}
              value={applications}
              onChange={(event) => setApplications(Math.max(0, Number(event.target.value) || 0))}
              className="w-14 rounded-lg border border-zinc-700 bg-zinc-950/60 py-1.5 text-center text-sm tabular-nums text-zinc-100 focus:border-emerald-600 focus:outline-none"
            />
            <button
              type="button"
              onClick={() => setApplications((n) => n + 1)}
              aria-label="One more application"
              className="flex size-9 items-center justify-center rounded-lg border border-zinc-700 text-lg text-zinc-300 hover:border-zinc-500"
            >
              +
            </button>
          </div>
        </div>
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          rows={2}
          placeholder="Anything worth remembering about today (optional)"
          aria-label="Evening note"
          className="resize-none rounded-xl border border-zinc-700 bg-zinc-950/60 px-3.5 py-3 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-emerald-600 focus:outline-none"
        />
        <Button type="submit" disabled={submitting}>
          {submitting ? "Reflecting..." : "Close out the day"}
        </Button>
        {error && <ErrorNote>{error}</ErrorNote>}
      </form>
    </Card>
  );
}

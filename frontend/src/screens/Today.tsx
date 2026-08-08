import { useState } from "react";

import { api } from "../api/client";
import type { Task } from "../api/types";
import { AgendaStrip } from "../components/AgendaStrip";
import { EveningForm } from "../components/EveningForm";
import { MorningComposer } from "../components/MorningComposer";
import { ProgressCard } from "../components/ProgressCard";
import { TaskList } from "../components/TaskList";
import { Card, ErrorNote, SectionLabel, Spinner } from "../components/ui";
import { formatDateLong } from "../lib/time";
import { useApi } from "../lib/useApi";

export function TodayScreen() {
  const today = useApi(api.today);
  const progress = useApi(api.progressSummary);
  const calendar = useApi(api.calendarToday);
  const [revising, setRevising] = useState(false);
  const [overrides, setOverrides] = useState<Record<number, boolean>>({});
  const [toggleError, setToggleError] = useState<string>();

  const plan = today.data?.plan ?? null;
  const checkin = today.data?.checkin ?? null;
  // Done-state overrides make toggles feel instant; a failed PATCH reverts.
  const tasks: Task[] = (today.data?.tasks ?? []).map((task) => ({
    ...task,
    done: overrides[task.id] ?? task.done,
  }));

  function toggleTask(task: Task) {
    const next = !task.done;
    setOverrides((current) => ({ ...current, [task.id]: next }));
    setToggleError(undefined);
    api.setTaskDone(task.id, next).catch((err: unknown) => {
      setOverrides((current) => {
        const reverted = { ...current };
        delete reverted[task.id];
        return reverted;
      });
      setToggleError(err instanceof Error ? err.message : "Could not update the task.");
    });
  }

  function afterPlanned() {
    setRevising(false);
    setOverrides({});
    today.reload();
    calendar.reload(); // new blocks may have landed in the calendar
  }

  function afterEvening() {
    today.reload();
    progress.reload(); // the check-in just moved the numbers
  }

  return (
    <div className="flex flex-col gap-4">
      <header>
        <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-zinc-500">
          {today.data ? formatDateLong(today.data.date) : ""}
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight text-zinc-50">Today</h1>
      </header>

      {today.loading && !today.data && <Spinner label="Loading your day" />}
      {today.error && !today.data && (
        <ErrorNote>
          {today.error}{" "}
          <button onClick={today.reload} className="underline">
            Try again
          </button>
        </ErrorNote>
      )}

      {today.data && (plan === null || revising) && (
        <MorningComposer
          initialText={revising ? (plan?.raw_input ?? "") : ""}
          onPlanned={afterPlanned}
          onCancel={revising ? () => setRevising(false) : undefined}
        />
      )}

      {plan && !revising && (
        <TaskList
          plan={plan}
          tasks={tasks}
          onToggle={toggleTask}
          onRevise={() => setRevising(true)}
        />
      )}
      {toggleError && <ErrorNote>{toggleError}</ErrorNote>}

      <AgendaStrip calendar={calendar.data} tasks={tasks} />

      {progress.data && <ProgressCard summary={progress.data} />}

      {today.data && checkin === null && <EveningForm tasks={tasks} onDone={afterEvening} />}
      {checkin && (
        <Card>
          <SectionLabel>Evening reflection</SectionLabel>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-zinc-200">
            {checkin.reflection}
          </p>
          <p className="mt-3 text-xs text-zinc-500">
            {checkin.applications_sent} applications logged
            {checkin.note ? ` · ${checkin.note}` : ""}
          </p>
        </Card>
      )}
    </div>
  );
}

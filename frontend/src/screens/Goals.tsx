import { useState } from "react";

import { api } from "../api/client";
import type { Goal } from "../api/types";
import { PlusIcon } from "../components/icons";
import {
  Button,
  Card,
  ErrorNote,
  PaceBadge,
  ProgressBar,
  SectionLabel,
  Spinner,
} from "../components/ui";
import { formatNumber } from "../lib/format";
import { formatDateShort } from "../lib/time";
import { useApi } from "../lib/useApi";

export function GoalsScreen() {
  const goals = useApi(api.goals);
  const [creating, setCreating] = useState(false);

  return (
    <div className="flex flex-col gap-4">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-50">Goals</h1>
        <button
          onClick={() => setCreating((value) => !value)}
          aria-label="New goal"
          className="flex size-9 items-center justify-center rounded-full border border-zinc-700 text-zinc-300 hover:border-zinc-500"
        >
          <PlusIcon className="size-4.5" />
        </button>
      </header>

      {creating && (
        <NewGoalForm
          bigGoals={(goals.data ?? []).filter((goal) => goal.level === "big")}
          onCreated={() => {
            setCreating(false);
            goals.reload();
          }}
        />
      )}

      {goals.loading && !goals.data && <Spinner label="Loading goals" />}
      {goals.error && !goals.data && <ErrorNote>{goals.error}</ErrorNote>}
      {goals.data?.length === 0 && !creating && (
        <p className="text-sm text-zinc-500">
          No goals yet. Add the big one first; monthly goals hang off it.
        </p>
      )}

      {(goals.data ?? []).map((goal) => (
        <BigGoalCard key={goal.id} goal={goal} onChanged={goals.reload} />
      ))}
    </div>
  );
}

function BigGoalCard({ goal, onChanged }: { goal: Goal; onChanged: () => void }) {
  const rollup = goal.children_rollup;
  return (
    <Card>
      <SectionLabel>Big goal</SectionLabel>
      <h2 className="mt-1 text-lg font-medium text-zinc-100">{goal.title}</h2>
      <div className="mt-1 flex flex-wrap gap-x-3 text-xs text-zinc-500">
        {goal.target_date && <span>by {formatDateShort(goal.target_date)}</span>}
        {rollup && (
          <span>
            {rollup.on_track} on track · {rollup.behind} behind · {rollup.done} done
          </span>
        )}
      </div>
      {goal.children.length > 0 && (
        <ul className="mt-4 space-y-4">
          {goal.children.map((child) => (
            <MonthlyGoalRow key={child.id} goal={child} onChanged={onChanged} />
          ))}
        </ul>
      )}
    </Card>
  );
}

function MonthlyGoalRow({ goal, onChanged }: { goal: Goal; onChanged: () => void }) {
  const [logging, setLogging] = useState(false);
  const [delta, setDelta] = useState("1");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();
  const metric = goal.target_value !== null;
  const done = goal.status === "done";

  async function save(event: React.FormEvent) {
    event.preventDefault();
    const amount = Number(delta);
    if (!amount || saving) return;
    setSaving(true);
    setError(undefined);
    try {
      await api.addProgress(goal.id, amount);
      setLogging(false);
      setDelta("1");
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not log progress.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <li>
      <div className="flex items-center justify-between gap-2">
        <span
          className={`min-w-0 flex-1 truncate text-sm ${
            done ? "text-zinc-500 line-through" : "text-zinc-200"
          }`}
        >
          {goal.title}
        </span>
        {goal.pace && !done && <PaceBadge status={goal.pace.status} />}
        {metric && !done && (
          <button
            onClick={() => setLogging((value) => !value)}
            className="text-xs text-zinc-500 hover:text-zinc-300"
          >
            {logging ? "cancel" : "+ log"}
          </button>
        )}
      </div>
      {metric ? (
        <div className="mt-1.5 flex items-center gap-3">
          <div className="flex-1">
            <ProgressBar percent={goal.percent} />
          </div>
          <span className="shrink-0 text-xs tabular-nums text-zinc-400">
            {formatNumber(goal.current)} of {formatNumber(goal.target_value ?? 0)}
            {goal.unit ? ` ${goal.unit}` : ""}
          </span>
        </div>
      ) : (
        <p className="mt-1 text-xs text-zinc-500">
          {goal.tasks_done_7d} task{goal.tasks_done_7d === 1 ? "" : "s"} done in the last 7 days
          {goal.last_activity ? ` · last activity ${formatDateShort(goal.last_activity)}` : ""}
        </p>
      )}
      {logging && (
        <form onSubmit={save} className="mt-2 flex items-center gap-2">
          <input
            type="number"
            step="any"
            value={delta}
            onChange={(event) => setDelta(event.target.value)}
            aria-label={`Progress to log for ${goal.title}`}
            className="w-20 rounded-lg border border-zinc-700 bg-zinc-950/60 px-2 py-1.5 text-center text-sm tabular-nums text-zinc-100 focus:border-emerald-600 focus:outline-none"
          />
          {goal.unit && <span className="text-xs text-zinc-500">{goal.unit}</span>}
          <Button type="submit" disabled={saving || !Number(delta)} className="px-3 py-1.5">
            {saving ? "Saving" : "Log"}
          </Button>
        </form>
      )}
      {error && <ErrorNote>{error}</ErrorNote>}
    </li>
  );
}

function NewGoalForm({ bigGoals, onCreated }: { bigGoals: Goal[]; onCreated: () => void }) {
  const [title, setTitle] = useState("");
  const [parentId, setParentId] = useState<string>("");
  const [target, setTarget] = useState("");
  const [unit, setUnit] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!title.trim() || saving) return;
    setSaving(true);
    setError(undefined);
    const monthly = parentId !== "";
    const now = new Date();
    const first = new Date(now.getFullYear(), now.getMonth(), 1);
    const last = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    const iso = (d: Date) =>
      `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
        d.getDate(),
      ).padStart(2, "0")}`;
    try {
      await api.createGoal({
        level: monthly ? "monthly" : "big",
        title: title.trim(),
        parent_id: monthly ? Number(parentId) : null,
        target_value: target ? Number(target) : null,
        unit: unit.trim() || null,
        // A metric monthly goal paces against its month by default.
        period_start: monthly && target ? iso(first) : null,
        period_end: monthly && target ? iso(last) : null,
      });
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the goal.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <SectionLabel>New goal</SectionLabel>
      <form onSubmit={save} className="mt-3 flex flex-col gap-3">
        <input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="What are you going after?"
          aria-label="Goal title"
          className="rounded-xl border border-zinc-700 bg-zinc-950/60 px-3.5 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-emerald-600 focus:outline-none"
        />
        <select
          value={parentId}
          onChange={(event) => setParentId(event.target.value)}
          aria-label="Parent goal"
          className="rounded-xl border border-zinc-700 bg-zinc-950/60 px-3 py-2.5 text-sm text-zinc-300 focus:border-emerald-600 focus:outline-none"
        >
          <option value="">A big goal of its own</option>
          {bigGoals.map((goal) => (
            <option key={goal.id} value={goal.id}>
              Monthly, under: {goal.title}
            </option>
          ))}
        </select>
        <div className="flex gap-2">
          <input
            type="number"
            step="any"
            min="0"
            value={target}
            onChange={(event) => setTarget(event.target.value)}
            placeholder="Target (optional)"
            aria-label="Target value"
            className="w-36 rounded-xl border border-zinc-700 bg-zinc-950/60 px-3.5 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-emerald-600 focus:outline-none"
          />
          <input
            value={unit}
            onChange={(event) => setUnit(event.target.value)}
            placeholder="Unit, e.g. applications"
            aria-label="Unit"
            className="flex-1 rounded-xl border border-zinc-700 bg-zinc-950/60 px-3.5 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-emerald-600 focus:outline-none"
          />
        </div>
        <Button type="submit" disabled={!title.trim() || saving}>
          {saving ? "Creating" : "Create goal"}
        </Button>
        {error && <ErrorNote>{error}</ErrorNote>}
      </form>
    </Card>
  );
}

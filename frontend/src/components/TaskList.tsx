import type { Plan, Task } from "../api/types";
import { formatTimeRange } from "../lib/time";
import { CheckIcon } from "./icons";
import { Card, SectionLabel } from "./ui";

interface Props {
  plan: Plan;
  tasks: Task[];
  onToggle: (task: Task) => void;
  onRevise: () => void;
}

/** The day's plan: prioritized tasks with their time blocks. */
export function TaskList({ plan, tasks, onToggle, onRevise }: Props) {
  const doneCount = tasks.filter((task) => task.done).length;

  return (
    <Card>
      <div className="flex items-baseline justify-between">
        <SectionLabel>
          Today's plan
          {tasks.length > 0 && (
            <span className="ml-2 normal-case tracking-normal text-zinc-600">
              {doneCount}/{tasks.length}
            </span>
          )}
        </SectionLabel>
        <button onClick={onRevise} className="text-xs text-zinc-500 hover:text-zinc-300">
          Revise
        </button>
      </div>
      {plan.rationale && (
        <p className="mt-2 text-sm leading-relaxed text-zinc-400">{plan.rationale}</p>
      )}
      <ul className="mt-2 divide-y divide-zinc-800/70">
        {tasks.map((task) => (
          <li key={task.id}>
            <button
              onClick={() => onToggle(task)}
              role="checkbox"
              aria-checked={task.done}
              className="flex w-full items-center gap-3 py-3 text-left"
            >
              <span
                className={`flex size-5 shrink-0 items-center justify-center rounded-full border transition-colors ${
                  task.done ? "border-emerald-500 bg-emerald-500 text-zinc-950" : "border-zinc-600"
                }`}
              >
                {task.done && <CheckIcon className="size-3.5" />}
              </span>
              <span className="min-w-0 flex-1">
                <span
                  className={`block text-sm ${
                    task.done ? "text-zinc-500 line-through" : "text-zinc-100"
                  }`}
                >
                  {task.title}
                </span>
                {task.block_start && task.block_minutes && (
                  <span className="mt-0.5 block text-xs text-zinc-500">
                    {formatTimeRange(task.block_start, task.block_minutes)}
                  </span>
                )}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}

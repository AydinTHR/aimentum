import type { CalendarDay, Task } from "../api/types";
import { buildAgenda } from "../lib/agenda";
import { formatTime } from "../lib/time";
import { Card, SectionLabel } from "./ui";

interface Props {
  calendar: CalendarDay | undefined;
  tasks: Task[];
}

/** The day as one timeline: real meetings plus the plan's blocks. */
export function AgendaStrip({ calendar, tasks }: Props) {
  const agenda = buildAgenda(calendar?.events ?? [], tasks);
  const empty = agenda.items.length === 0 && agenda.allDay.length === 0;

  return (
    <Card>
      <SectionLabel>Agenda</SectionLabel>
      {calendar && !calendar.available && (
        <p className="mt-2 text-xs text-zinc-500">
          Calendar unreachable right now; showing planned blocks only.
        </p>
      )}
      {agenda.allDay.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {agenda.allDay.map((summary) => (
            <span
              key={summary}
              className="rounded-full border border-zinc-700 px-2.5 py-0.5 text-xs text-zinc-400"
            >
              {summary}
            </span>
          ))}
        </div>
      )}
      {empty ? (
        <p className="mt-3 text-sm text-zinc-500">Nothing scheduled.</p>
      ) : (
        <ul className="mt-3 space-y-1.5">
          {agenda.items.map((item) => (
            <li
              key={item.key}
              className={`flex items-baseline gap-3 rounded-lg border-l-2 py-1.5 pl-3 ${
                item.kind === "block"
                  ? "border-emerald-500/70 bg-emerald-500/[0.06]"
                  : "border-zinc-600 bg-zinc-800/40"
              }`}
            >
              <span className="w-20 shrink-0 text-xs tabular-nums text-zinc-400">
                {formatTime(item.start.toISOString())}
              </span>
              <span className="min-w-0 flex-1 truncate text-sm text-zinc-200">{item.title}</span>
              {item.kind === "block" && (
                <span className="pr-2 text-[10px] font-medium uppercase tracking-wider text-emerald-400/80">
                  block
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

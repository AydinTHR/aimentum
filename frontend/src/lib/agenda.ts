import type { CalendarEvent, Task } from "../api/types";

export interface AgendaItem {
  key: string;
  title: string;
  start: Date;
  end: Date;
  kind: "event" | "block";
}

export interface Agenda {
  allDay: string[];
  items: AgendaItem[];
}

/** One timeline from two sources: real calendar events plus the plan's
 * blocks. Blocks come from the API's task list, which is authoritative even
 * when Google is unreachable; events written to the app's own calendar are
 * dropped so a block never shows up twice. */
export function buildAgenda(
  events: CalendarEvent[],
  tasks: Task[],
  appCalendarName = "Aimentum",
): Agenda {
  const allDay = events.filter((event) => event.all_day).map((event) => event.summary);

  const timedEvents: AgendaItem[] = events
    .filter((event) => !event.all_day && event.calendar !== appCalendarName)
    .map((event, index) => ({
      key: `event-${index}`,
      title: event.summary,
      start: new Date(event.start),
      end: new Date(event.end),
      kind: "event" as const,
    }));

  const blocks: AgendaItem[] = tasks
    .filter(
      (task): task is Task & { block_start: string; block_minutes: number } =>
        task.block_start !== null && task.block_minutes !== null,
    )
    .map((task) => ({
      key: `block-${task.id}`,
      title: task.title,
      start: new Date(task.block_start),
      end: new Date(new Date(task.block_start).getTime() + task.block_minutes * 60_000),
      kind: "block" as const,
    }));

  const items = [...timedEvents, ...blocks].sort((a, b) => a.start.getTime() - b.start.getTime());
  return { allDay, items };
}

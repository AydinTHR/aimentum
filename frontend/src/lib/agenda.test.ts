import { describe, expect, it } from "vitest";

import type { CalendarEvent, Task } from "../api/types";
import { buildAgenda } from "./agenda";

function event(overrides: Partial<CalendarEvent> = {}): CalendarEvent {
  return {
    summary: "Standup",
    start: "2026-08-08T09:00:00-04:00",
    end: "2026-08-08T09:15:00-04:00",
    all_day: false,
    calendar: "Personal",
    ...overrides,
  };
}

function task(overrides: Partial<Task> = {}): Task {
  return {
    id: 1,
    plan_id: 1,
    title: "Apply to Shopify",
    monthly_goal_id: null,
    done: false,
    sort: 0,
    block_start: "2026-08-08T10:00:00-04:00",
    block_minutes: 60,
    gcal_event_id: "abc",
    ...overrides,
  };
}

describe("buildAgenda", () => {
  it("interleaves events and blocks in time order", () => {
    const agenda = buildAgenda(
      [event({ summary: "Standup", start: "2026-08-08T09:00:00-04:00" })],
      [
        task({ id: 1, title: "Deep work", block_start: "2026-08-08T08:00:00-04:00" }),
        task({ id: 2, title: "Applications", block_start: "2026-08-08T11:00:00-04:00" }),
      ],
    );

    expect(agenda.items.map((item) => item.title)).toEqual([
      "Deep work",
      "Standup",
      "Applications",
    ]);
    expect(agenda.items.map((item) => item.kind)).toEqual(["block", "event", "block"]);
  });

  it("drops events on the app's own calendar so blocks are not doubled", () => {
    const agenda = buildAgenda(
      [
        event({ summary: "Apply to Shopify", calendar: "Aimentum" }),
        event({ summary: "Dentist", calendar: "Personal" }),
      ],
      [task({ title: "Apply to Shopify" })],
    );

    expect(agenda.items.map((item) => item.title)).toEqual(["Dentist", "Apply to Shopify"]);
    expect(agenda.items.filter((item) => item.title === "Apply to Shopify")).toHaveLength(1);
  });

  it("separates all-day events, which reserve no time", () => {
    const agenda = buildAgenda([event({ summary: "Canada Day", all_day: true })], []);

    expect(agenda.allDay).toEqual(["Canada Day"]);
    expect(agenda.items).toEqual([]);
  });

  it("ignores tasks that have no block", () => {
    const agenda = buildAgenda([], [task({ block_start: null, block_minutes: null })]);
    expect(agenda.items).toEqual([]);
  });

  it("ends a block at start plus its length", () => {
    const agenda = buildAgenda(
      [],
      [task({ block_start: "2026-08-08T14:00:00-04:00", block_minutes: 45 })],
    );

    const [block] = agenda.items;
    expect(block.end.getTime() - block.start.getTime()).toBe(45 * 60_000);
  });
});

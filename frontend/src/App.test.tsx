import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { tokenStore } from "./api/client";

const TODAY = {
  date: "2026-08-08",
  plan: {
    id: 1,
    date: "2026-08-08",
    raw_input: "apply to shopify, gym at lunch",
    input_mode: "text",
    rationale: "Applications first while you are sharp.",
  },
  tasks: [
    {
      id: 7,
      plan_id: 1,
      title: "Apply to Shopify",
      monthly_goal_id: 2,
      done: false,
      sort: 0,
      block_start: "2026-08-08T09:30:00-04:00",
      block_minutes: 90,
      gcal_event_id: "evt-1",
    },
  ],
  checkin: null,
};

const PROGRESS = {
  date: "2026-08-08",
  applications_floor: 3,
  applications_sent_today: null,
  goals: [
    {
      id: 2,
      title: "40 quality applications",
      unit: "applications",
      current: 12,
      target: 40,
      percent: 30,
      pace: { expected: 10.32, status: "ahead" },
    },
  ],
};

const CALENDAR = {
  date: "2026-08-08",
  available: true,
  events: [
    {
      summary: "Recruiter call",
      start: "2026-08-08T13:00:00-04:00",
      end: "2026-08-08T13:30:00-04:00",
      all_day: false,
      calendar: "Personal",
    },
  ],
};

/** Routes by path so screens can fetch in any order. */
function routedFetch(overrides: Record<string, unknown> = {}) {
  const routes: Record<string, unknown> = {
    "/today": TODAY,
    "/progress/summary": PROGRESS,
    "/calendar/today": CALENDAR,
    "/settings": {
      applications_floor: 3,
      read_back_enabled: false,
      time_blocking_enabled: true,
      workday_start: "09:00:00",
      workday_end: "18:00:00",
    },
    "/goals": [],
    "/retros": [],
    ...overrides,
  };
  return vi.fn((input: string | URL | Request) => {
    // Match the exact pathname, not a suffix: /calendar/today ends with
    // /today and would otherwise be served the wrong payload.
    const { pathname } = new URL(
      typeof input === "string" ? input : input.toString(),
      "http://localhost",
    );
    if (!(pathname in routes)) return Promise.resolve(new Response("{}", { status: 404 }));
    return Promise.resolve(
      new Response(JSON.stringify(routes[pathname]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
  });
}

describe("App", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockImplementation(routedFetch() as unknown as typeof fetch);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the token gate when there is no token", () => {
    render(<App />);
    expect(screen.getByLabelText("Access token")).toBeInTheDocument();
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });

  it("lets the owner in once the token is accepted", async () => {
    render(<App />);

    await userEvent.type(screen.getByLabelText("Access token"), "secret");
    await userEvent.click(screen.getByRole("button", { name: "Unlock" }));

    expect(await screen.findByRole("heading", { name: "Today" })).toBeInTheDocument();
    expect(tokenStore.get()).toBe("secret");
  });

  it("keeps the gate up and reports the reason when the token is wrong", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Not authenticated" }), { status: 401 }),
    );
    render(<App />);

    await userEvent.type(screen.getByLabelText("Access token"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Unlock" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/not accepted/i);
    expect(screen.getByLabelText("Access token")).toBeInTheDocument();
    // A rejected token is never stored, so the app never flashes into view.
    expect(tokenStore.get()).toBeNull();
  });

  describe("once unlocked", () => {
    beforeEach(() => {
      tokenStore.set("test-token");
    });

    it("renders the plan, its blocks, and the pace-aware progress", async () => {
      render(<App />);

      // The title shows twice on purpose: once as a task, once as its block.
      expect(await screen.findByRole("checkbox", { name: /Apply to Shopify/ })).toBeVisible();
      expect(screen.getByText("Applications first while you are sharp.")).toBeInTheDocument();
      expect(screen.getByText("9:30 AM to 11:00 AM")).toBeInTheDocument();
      expect(await screen.findByText("40 quality applications")).toBeInTheDocument();
      expect(screen.getByText("12 of 40 applications")).toBeInTheDocument();
      expect(screen.getByText("ahead")).toBeInTheDocument();
      expect(screen.getByText(/pace expects 10.32 by today/)).toBeInTheDocument();
    });

    it("merges calendar events with planned blocks in the agenda", async () => {
      render(<App />);

      const agenda = (await screen.findByText("Agenda")).closest("section");
      expect(agenda).not.toBeNull();
      const rows = agenda!.querySelectorAll("li");
      expect([...rows].map((row) => row.textContent)).toEqual([
        expect.stringContaining("Apply to Shopify"),
        expect.stringContaining("Recruiter call"),
      ]);
    });

    it("checks a task off optimistically and tells the API", async () => {
      const fetchMock = vi.fn((input: string | URL | Request, _init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url.endsWith("/tasks/7")) {
          return Promise.resolve(
            new Response(JSON.stringify({ ...TODAY.tasks[0], done: true }), { status: 200 }),
          );
        }
        return routedFetch()(input);
      });
      vi.spyOn(globalThis, "fetch").mockImplementation(fetchMock as unknown as typeof fetch);
      render(<App />);

      const task = await screen.findByRole("checkbox", { name: /Apply to Shopify/ });
      expect(task).toHaveAttribute("aria-checked", "false");

      await userEvent.click(task);

      expect(task).toHaveAttribute("aria-checked", "true");
      await waitFor(() => {
        const patch = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/tasks/7"));
        expect(patch?.[1]?.method).toBe("PATCH");
      });
    });

    it("reverts the checkbox when the API rejects the change", async () => {
      vi.spyOn(globalThis, "fetch").mockImplementation(((input: string | URL | Request) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url.endsWith("/tasks/7")) {
          return Promise.resolve(
            new Response(JSON.stringify({ detail: "task is gone" }), { status: 404 }),
          );
        }
        return routedFetch()(input);
      }) as unknown as typeof fetch);
      render(<App />);

      const task = await screen.findByRole("checkbox", { name: /Apply to Shopify/ });
      await userEvent.click(task);

      await waitFor(() => expect(task).toHaveAttribute("aria-checked", "false"));
      expect(await screen.findByRole("alert")).toHaveTextContent("task is gone");
    });

    it("moves between screens from the bottom nav", async () => {
      render(<App />);
      await screen.findByRole("heading", { name: "Today" });

      await userEvent.click(screen.getByRole("button", { name: "Retros" }));

      expect(await screen.findByRole("heading", { name: "Retros" })).toBeInTheDocument();
      expect(screen.queryByRole("heading", { name: "Today" })).not.toBeInTheDocument();
    });

    it("asks for a morning check-in when there is no plan yet", async () => {
      vi.spyOn(globalThis, "fetch").mockImplementation(
        routedFetch({
          "/today": { date: "2026-08-08", plan: null, tasks: [], checkin: null },
        }) as unknown as typeof fetch,
      );
      render(<App />);

      expect(await screen.findByLabelText("Morning check-in")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Make my plan" })).toBeDisabled();
    });
  });
});

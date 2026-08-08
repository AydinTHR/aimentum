import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

import {
  formatDateLong,
  formatDateShort,
  formatMinutes,
  formatTime,
  formatTimeRange,
} from "./time";

/** Pretend the device is nowhere near Toronto.
 *
 * CI runs in UTC and a laptop can be set to anything, so the display must not
 * depend on where the browser thinks it is. Without this the suite would only
 * ever prove the behaviour on a machine already in the right timezone.
 */
describe.each([
  ["UTC", 0],
  ["Asia/Tokyo", -540],
  ["Pacific/Auckland", -780],
])("with the device in %s", (_label, offsetMinutes) => {
  beforeAll(() => {
    vi.spyOn(Date.prototype, "getTimezoneOffset").mockReturnValue(offsetMinutes);
  });
  afterAll(() => {
    vi.restoreAllMocks();
  });

  it("renders a block at the hour the plan meant", () => {
    expect(formatTime("2026-08-08T09:30:00-04:00")).toBe("9:30 AM");
  });

  it("renders a range across its full length", () => {
    expect(formatTimeRange("2026-08-08T09:30:00-04:00", 90)).toBe("9:30 AM to 11:00 AM");
  });

  it("keeps a late block on the day it belongs to", () => {
    // The mirror of the backend fix: 20:30 local is tomorrow in UTC.
    expect(formatTime("2026-08-08T20:30:00-04:00")).toBe("8:30 PM");
  });

  it("does not shift a date-only string onto a neighbouring day", () => {
    expect(formatDateLong("2026-08-08")).toBe("Saturday, August 8");
    expect(formatDateShort("2026-08-08")).toBe("Aug 8");
  });
});

describe("formatMinutes", () => {
  it("reads naturally at every length", () => {
    expect(formatMinutes(45)).toBe("45 min");
    expect(formatMinutes(60)).toBe("1 h");
    expect(formatMinutes(90)).toBe("1 h 30 min");
    expect(formatMinutes(240)).toBe("4 h");
  });
});

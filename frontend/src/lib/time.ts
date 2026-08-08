/** Display helpers.
 *
 * Everything renders in the owner's timezone, never the device's. The backend
 * goes out of its way to serialize datetimes in America/Toronto, and a device
 * set elsewhere (travelling, or a machine left on UTC) would otherwise show a
 * block at an hour the plan never meant and the calendar does not agree with.
 */
const USER_TIMEZONE = "America/Toronto";

const TIME_FORMAT: Intl.DateTimeFormatOptions = {
  hour: "numeric",
  minute: "2-digit",
  timeZone: USER_TIMEZONE,
};

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", TIME_FORMAT);
}

export function formatTimeRange(startIso: string, minutes: number): string {
  const start = new Date(startIso);
  const end = new Date(start.getTime() + minutes * 60_000);
  return `${formatTime(startIso)} to ${end.toLocaleTimeString("en-US", TIME_FORMAT)}`;
}

/** Date-only strings have no timezone, so they are read and rendered as UTC.
 * Anything else lets a device offset shift "today" onto the wrong day. */
function fromDateOnly(dateStr: string): Date {
  const [year, month, day] = dateStr.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

/** "Friday, August 8" */
export function formatDateLong(dateStr: string): string {
  return fromDateOnly(dateStr).toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  });
}

export function formatDateShort(dateStr: string): string {
  return fromDateOnly(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** "45 min" or "1 h 30 min", for block lengths. */
export function formatMinutes(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours} h` : `${hours} h ${rest} min`;
}

/** Display helpers. The API already serializes datetimes in the owner's
 * timezone (America/Toronto), so rendering uses the device clock, which is
 * the same place. */

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

export function formatTimeRange(startIso: string, minutes: number): string {
  const start = new Date(startIso);
  const end = new Date(start.getTime() + minutes * 60_000);
  return `${formatTime(startIso)} to ${end.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  })}`;
}

/** "Friday, August 8" from a date-only string, parsed as local so the day
 * never shifts across midnight UTC. */
export function formatDateLong(dateStr: string): string {
  const [year, month, day] = dateStr.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString([], {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

export function formatDateShort(dateStr: string): string {
  const [year, month, day] = dateStr.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString([], {
    month: "short",
    day: "numeric",
  });
}

/** "45 min" or "1 h 30 min", for block lengths. */
export function formatMinutes(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours} h` : `${hours} h ${rest} min`;
}

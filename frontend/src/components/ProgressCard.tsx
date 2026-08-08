import type { ProgressSummary } from "../api/types";
import { formatNumber } from "../lib/format";
import { Card, PaceBadge, ProgressBar, SectionLabel } from "./ui";

/** Honest pace, not vanity progress: every metric goal shows where you are
 * against where the calendar says you should be. */
export function ProgressCard({ summary }: { summary: ProgressSummary }) {
  const sentToday = summary.applications_sent_today;

  return (
    <Card>
      <SectionLabel>Progress</SectionLabel>
      <div className="mt-3 flex items-baseline justify-between">
        <span className="text-sm text-zinc-300">Applications today</span>
        <span className="text-sm tabular-nums text-zinc-200">
          {sentToday === null ? (
            <span className="text-zinc-500">logs at evening check-in</span>
          ) : (
            `${sentToday} of ${summary.applications_floor}`
          )}
        </span>
      </div>
      {summary.goals.length > 0 && (
        <ul className="mt-4 space-y-4">
          {summary.goals.map((goal) => (
            <li key={goal.id}>
              <div className="flex items-center justify-between gap-2">
                <span className="min-w-0 flex-1 truncate text-sm text-zinc-200">{goal.title}</span>
                {goal.pace && <PaceBadge status={goal.pace.status} />}
              </div>
              <div className="mt-1.5 flex items-center gap-3">
                <div className="flex-1">
                  <ProgressBar percent={goal.percent} />
                </div>
                <span className="shrink-0 text-xs tabular-nums text-zinc-400">
                  {formatNumber(goal.current)}
                  {goal.target !== null && ` of ${formatNumber(goal.target)}`}
                  {goal.unit ? ` ${goal.unit}` : ""}
                </span>
              </div>
              {goal.pace && (
                <p className="mt-1 text-xs text-zinc-500">
                  pace expects {formatNumber(goal.pace.expected)} by today
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

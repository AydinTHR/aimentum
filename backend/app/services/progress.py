"""All progress and pace math lives here and nowhere else.

Rules encoded in this module, fixed by the product spec:

- A percent only exists where a real denominator exists (a metric goal with a
  target). Vague goals never get a fake number.
- Pace compares the fraction of the target reached against the fraction of the
  period elapsed, with a 10 percentage point band: within the band is on track,
  above it is ahead, below it is behind. The band edges themselves count as on
  track. Elapsed days are counted inclusively: on the first day of a 31 day
  period, 1/31 of the period has elapsed.
- Auto sources log progress from behavior: the evening applications count is
  upserted (source "evening_checkin", one entry per goal per day, so editing a
  check-in never double counts), and completing a linked task adds one unit
  (source "task", removed again when the task is unchecked).

Claude interprets these numbers in prompts; it never computes them.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AppSettings,
    AutoSource,
    Checkin,
    DailyPlan,
    Goal,
    GoalStatus,
    ProgressLog,
    ProgressSource,
    Task,
)

PaceStatus = Literal["ahead", "on_track", "behind"]

PACE_BAND = 0.10


@dataclass(frozen=True)
class Pace:
    expected: float
    status: PaceStatus


def month_bounds(day: date) -> tuple[date, date]:
    """First and last day of the calendar month containing `day`."""
    start = day.replace(day=1)
    next_month = (start + timedelta(days=32)).replace(day=1)
    return start, next_month - timedelta(days=1)


def compute_pace(
    target: Decimal | None,
    current: Decimal,
    period_start: date | None,
    period_end: date | None,
    today: date,
) -> Pace | None:
    """Pace for a metric goal, or None when no honest pace exists.

    None when the target is missing or zero, the period is missing, or the
    period is inverted. Days before the period count as zero elapsed; days
    after it count as fully elapsed.
    """
    if target is None or target <= 0:
        return None
    if period_start is None or period_end is None or period_end < period_start:
        return None

    total_days = (period_end - period_start).days + 1
    elapsed_days = (today - period_start).days + 1
    elapsed_days = max(0, min(elapsed_days, total_days))
    elapsed_fraction = elapsed_days / total_days

    expected = float(target) * elapsed_fraction
    diff = float(current) / float(target) - elapsed_fraction
    status: PaceStatus
    if diff > PACE_BAND:
        status = "ahead"
    elif diff < -PACE_BAND:
        status = "behind"
    else:
        status = "on_track"
    return Pace(expected=round(expected, 2), status=status)


def goal_current(session: Session, goal_id: int) -> Decimal:
    total = session.execute(
        select(func.coalesce(func.sum(ProgressLog.delta), 0)).where(ProgressLog.goal_id == goal_id)
    ).scalar_one()
    return Decimal(total)


def goal_percent(current: Decimal, target: Decimal | None) -> float | None:
    if target is None or target <= 0:
        return None
    return round(float(current) / float(target) * 100, 1)


def add_progress(
    session: Session,
    goal: Goal,
    delta: Decimal,
    source: ProgressSource,
    day: date,
    note: str | None = None,
) -> ProgressLog:
    entry = ProgressLog(goal_id=goal.id, date=day, delta=delta, source=source, note=note)
    session.add(entry)
    session.flush()
    return entry


def record_applications(session: Session, day: date, count: int) -> None:
    """Log the evening applications count against every matching goal.

    Idempotent: one "evening_checkin" entry per goal per day, set to the
    latest count, so editing a check-in re-sets the value rather than adding
    to it. Applies to active goals with the applications auto source whose
    period contains the day (goals without a period always match).
    """
    goals = session.scalars(
        select(Goal).where(
            Goal.auto_source == AutoSource.APPLICATIONS,
            Goal.status == GoalStatus.ACTIVE,
        )
    ).all()
    for goal in goals:
        if goal.period_start is not None and day < goal.period_start:
            continue
        if goal.period_end is not None and day > goal.period_end:
            continue
        existing = session.scalars(
            select(ProgressLog).where(
                ProgressLog.goal_id == goal.id,
                ProgressLog.date == day,
                ProgressLog.source == ProgressSource.EVENING_CHECKIN,
            )
        ).first()
        if existing is None:
            add_progress(session, goal, Decimal(count), ProgressSource.EVENING_CHECKIN, day=day)
        else:
            existing.delta = Decimal(count)
            session.flush()


def sync_task_progress(session: Session, task: Task, done: bool, day: date) -> None:
    """Keep the ledger in step with a task's done state.

    Completing a task linked to a "tasks_done" goal adds one unit; unchecking
    removes one previously added unit. Only transitions log anything, so the
    caller must invoke this only when the done state actually changes.
    """
    if task.monthly_goal_id is None:
        return
    goal = session.get(Goal, task.monthly_goal_id)
    if goal is None or goal.auto_source != AutoSource.TASKS_DONE:
        return
    if done:
        add_progress(session, goal, Decimal(1), ProgressSource.TASK, day=day)
    else:
        entry = session.scalars(
            select(ProgressLog)
            .where(
                ProgressLog.goal_id == goal.id,
                ProgressLog.source == ProgressSource.TASK,
                ProgressLog.delta == Decimal(1),
            )
            .order_by(ProgressLog.id.desc())
        ).first()
        if entry is not None:
            session.delete(entry)
            session.flush()


def last_activity(session: Session, goal_id: int) -> date | None:
    return session.execute(
        select(func.max(ProgressLog.date)).where(ProgressLog.goal_id == goal_id)
    ).scalar_one()


def tasks_done_last_7_days(session: Session, goal_id: int, today: date) -> int:
    """Completed tasks linked to the goal whose plan date falls in the past 7 days."""
    since = today - timedelta(days=6)
    count = session.execute(
        select(func.count(Task.id))
        .join(DailyPlan, Task.plan_id == DailyPlan.id)
        .where(
            Task.monthly_goal_id == goal_id,
            Task.done.is_(True),
            DailyPlan.date >= since,
            DailyPlan.date <= today,
        )
    ).scalar_one()
    return int(count)


def get_settings_row(session: Session) -> AppSettings:
    row = session.get(AppSettings, 1)
    if row is None:
        row = AppSettings(id=1)
        session.add(row)
        session.flush()
    return row


def progress_summary(session: Session, today: date) -> dict[str, object]:
    """The Today card payload: floor progress plus each active metric goal."""
    settings_row = get_settings_row(session)
    checkin = session.scalars(select(Checkin).where(Checkin.date == today)).first()

    goals_payload: list[dict[str, object]] = []
    metric_goals = session.scalars(
        select(Goal)
        .where(Goal.status == GoalStatus.ACTIVE, Goal.target_value.is_not(None))
        .order_by(Goal.id)
    ).all()
    for goal in metric_goals:
        current = goal_current(session, goal.id)
        pace = compute_pace(goal.target_value, current, goal.period_start, goal.period_end, today)
        goals_payload.append(
            {
                "id": goal.id,
                "title": goal.title,
                "unit": goal.unit,
                "current": float(current),
                "target": float(goal.target_value) if goal.target_value is not None else None,
                "percent": goal_percent(current, goal.target_value),
                "pace": None
                if pace is None
                else {"expected": pace.expected, "status": pace.status},
            }
        )

    return {
        "date": today.isoformat(),
        "applications_floor": settings_row.applications_floor,
        "applications_sent_today": None if checkin is None else checkin.applications_sent,
        "goals": goals_payload,
    }

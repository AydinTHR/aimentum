"""The agent brain: morning planning, evening reflection, weekly retro.

Claude interprets numbers and writes text; every number in its context comes
from the progress service. Tone rules are enforced here in code: hard length
caps (reflection 400 chars, retro 1200 chars) and an em dash sweep, because
generated copy must follow the same prose rules as the rest of the product.
"""

import json
import logging
from dataclasses import dataclass
from datetime import date, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AppSettings,
    Checkin,
    DailyPlan,
    Goal,
    GoalLevel,
    GoalStatus,
    InputMode,
    Retro,
    Task,
)
from app.services import progress as progress_service
from app.services.calendar import CalendarEvent, CalendarService, CalendarUnavailable
from app.services.llm import LlmClient, load_prompt
from app.services.progress import format_number
from app.services.scheduling import BlockProposal, schedule_blocks

logger = logging.getLogger(__name__)

REFLECTION_MAX_CHARS = 400
RETRO_MAX_CHARS = 1200
MAX_TASKS_PER_PLAN = 10


def sanitize_copy(text: str, max_chars: int) -> str:
    """Enforce the tone rules the prompt asks for, in code."""
    cleaned = text.replace("\u2014", ", ").replace("\u2015", ", ").strip()
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rstrip()
    return cleaned


def _goal_context_lines(session: Session, today: date) -> tuple[str, set[int]]:
    """Human-readable goal tree with pace numbers, plus the valid monthly ids."""
    lines: list[str] = []
    valid_ids: set[int] = set()
    monthly_goals = session.scalars(
        select(Goal)
        .where(Goal.level == GoalLevel.MONTHLY, Goal.status == GoalStatus.ACTIVE)
        .order_by(Goal.id)
    ).all()
    for goal in monthly_goals:
        valid_ids.add(goal.id)
        current = progress_service.goal_current(session, goal.id)
        pace = progress_service.compute_pace(
            goal.target_value, current, goal.period_start, goal.period_end, today
        )
        if goal.target_value is not None and pace is not None:
            lines.append(
                f"- goal id {goal.id}: {goal.title}:"
                f" {format_number(current)} of {format_number(goal.target_value)}"
                f" {goal.unit or 'units'}, expected {format_number(pace.expected)} by today,"
                f" status {pace.status.replace('_', ' ')}"
            )
        else:
            lines.append(f"- goal id {goal.id}: {goal.title} (no metric target)")
    if not lines:
        lines.append("- no active monthly goals yet")
    return "\n".join(lines), valid_ids


@dataclass(frozen=True)
class ParsedTask:
    title: str
    monthly_goal_id: int | None
    proposal: BlockProposal | None = None


def _parse_morning_json(text: str, valid_goal_ids: set[int]) -> tuple[list[ParsedTask], str] | None:
    """Parse Claude's strict JSON defensively; None means fall back."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    raw_tasks = payload.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        return None

    tasks: list[ParsedTask] = []
    for index, entry in enumerate(raw_tasks[:MAX_TASKS_PER_PLAN]):
        if not isinstance(entry, dict):
            return None
        title = entry.get("title")
        if not isinstance(title, str) or not title.strip():
            return None
        goal_id = entry.get("monthly_goal_id")
        if not isinstance(goal_id, int) or goal_id not in valid_goal_ids:
            goal_id = None
        tasks.append(
            ParsedTask(
                title=title.strip()[:300],
                monthly_goal_id=goal_id,
                proposal=_parse_block_proposal(entry, index),
            )
        )

    rationale = payload.get("rationale")
    rationale_text = rationale.strip() if isinstance(rationale, str) else ""
    return tasks, sanitize_copy(rationale_text, 300)


def _parse_block_proposal(entry: dict[str, object], index: int) -> BlockProposal | None:
    """Read the optional block fields; anything malformed just means no block."""
    raw_start = entry.get("block_start")
    raw_minutes = entry.get("block_minutes")
    if not isinstance(raw_start, str) or not isinstance(raw_minutes, int) or raw_minutes <= 0:
        return None
    try:
        start = time.fromisoformat(raw_start)
    except ValueError:
        return None
    return BlockProposal(task_index=index, start=start, minutes=raw_minutes)


def _event_lines(events: list[CalendarEvent], available: bool) -> str:
    if not available:
        return "unavailable, so plan without knowing today's meetings"
    if not events:
        return "nothing scheduled"
    lines = []
    for event in events:
        when = (
            "all day"
            if event.all_day
            else (f"{event.start.strftime('%H:%M')} to {event.end.strftime('%H:%M')}")
        )
        lines.append(f"- {when}: {event.summary}")
    return "\n" + "\n".join(lines)


def _read_calendar(
    calendar: CalendarService | None, today: date
) -> tuple[list[CalendarEvent], bool]:
    """Today's events, plus whether the calendar answered at all."""
    if calendar is None:
        return [], False
    try:
        return calendar.list_events(today), True
    except CalendarUnavailable as error:
        logger.warning("calendar unavailable for %s: %s", today, error)
        return [], False


def _clear_blocks(calendar: CalendarService | None, plan: DailyPlan) -> None:
    """Remove the calendar events a superseded plan created."""
    if calendar is None:
        return
    for task in plan.tasks:
        if not task.gcal_event_id:
            continue
        try:
            calendar.delete_block(task.gcal_event_id)
        except CalendarUnavailable as error:
            logger.warning("could not delete block %s: %s", task.gcal_event_id, error)


def plan_morning(
    session: Session,
    llm: LlmClient,
    raw_text: str,
    input_mode: InputMode,
    today: date,
    calendar: CalendarService | None = None,
) -> DailyPlan:
    """Parse and prioritize the morning check-in into today's plan.

    Re-submitting replaces today's plan: the previous plan, its tasks, and
    the calendar blocks it created are removed so a re-plan starts clean.
    Parsing never asks questions; if the JSON cannot be salvaged, the
    fallback is one task holding the raw text.

    The calendar is optional on purpose. If it cannot be reached the plan is
    still made, without meetings and without time blocks, and the rationale
    says so rather than quietly pretending the day is empty.
    """
    goal_lines, valid_ids = _goal_context_lines(session, today)
    settings_row = progress_service.get_settings_row(session)
    checkin = session.scalars(select(Checkin).where(Checkin.date == today)).first()
    events, calendar_available = _read_calendar(calendar, today)
    blocking_on = settings_row.time_blocking_enabled and calendar_available

    applications_line = (
        f"applications floor: {settings_row.applications_floor} per day;"
        f" logged today so far: {checkin.applications_sent if checkin else 0}"
    )
    context = (
        f"Today is {today.isoformat()}.\n"
        f"{applications_line}\n"
        f"Today's calendar events: {_event_lines(events, calendar_available)}\n"
        f"Workday window: {settings_row.workday_start.strftime('%H:%M')}"
        f" to {settings_row.workday_end.strftime('%H:%M')}\n"
        f"Active monthly goals:\n{goal_lines}"
    )
    blocking_instruction = (
        "propose block_start (HH:MM, 24 hour) and block_minutes for each task "
        "that deserves a slot, inside the workday window and clear of the "
        "events above. Leave both null for anything that does not need one."
        if blocking_on
        else "disabled today. Set block_start and block_minutes to null on every task."
    )

    prompt = load_prompt("morning_prioritize_v1.txt").substitute(
        context=context, raw_text=raw_text, blocking_instruction=blocking_instruction
    )
    parsed = _parse_morning_json(llm.complete_daily(prompt), valid_ids)
    tasks: list[ParsedTask]
    if parsed is None:
        tasks = [ParsedTask(title=raw_text.strip()[:300] or "Plan the day", monthly_goal_id=None)]
        rationale = "Saved as one task because the plan could not be parsed."
    else:
        tasks, rationale = parsed

    if not calendar_available and calendar is not None:
        rationale = sanitize_copy(
            f"{rationale} Calendar was unreachable, so this plan does not account "
            "for meetings.".strip(),
            300,
        )

    existing = session.scalars(select(DailyPlan).where(DailyPlan.date == today)).first()
    if existing is not None:
        _clear_blocks(calendar, existing)
        session.delete(existing)
        session.flush()

    plan = DailyPlan(
        date=today, raw_input=raw_text, input_mode=input_mode, rationale=rationale or None
    )
    session.add(plan)
    session.flush()

    rows: list[Task] = []
    for sort, parsed_task in enumerate(tasks):
        row = Task(
            plan_id=plan.id,
            title=parsed_task.title,
            monthly_goal_id=parsed_task.monthly_goal_id,
            sort=sort,
        )
        session.add(row)
        rows.append(row)
    session.flush()

    if blocking_on and calendar is not None:
        _write_blocks(calendar, rows, tasks, events, today, settings_row)
        session.flush()
    return plan


def _write_blocks(
    calendar: CalendarService,
    rows: list[Task],
    tasks: list[ParsedTask],
    events: list[CalendarEvent],
    today: date,
    settings_row: AppSettings,
) -> None:
    """Validate the proposed blocks in code, then write the survivors."""
    proposals = [task.proposal for task in tasks if task.proposal is not None]
    blocks = schedule_blocks(
        proposals, events, today, settings_row.workday_start, settings_row.workday_end
    )
    for block in blocks:
        row = rows[block.task_index]
        try:
            row.gcal_event_id = calendar.create_block(row.title, block.start, block.minutes)
        except CalendarUnavailable as error:
            logger.warning("could not write block for task %s: %s", row.title, error)
            continue
        row.block_start = block.start
        row.block_minutes = block.minutes


def submit_evening(
    session: Session,
    llm: LlmClient,
    applications_sent: int,
    note: str | None,
    task_states: list[tuple[int, bool]],
    today: date,
) -> Checkin:
    """Close the day: apply task states, log applications, write the reflection.

    Editing an existing check-in is safe: the applications count is upserted
    per goal per day by the progress service, and the reflection is
    regenerated from the corrected numbers.
    """
    for task_id, done in task_states:
        task = session.get(Task, task_id)
        if task is None or task.done == done:
            continue
        task.done = done
        progress_service.sync_task_progress(session, task, done, today)

    progress_service.record_applications(session, today, applications_sent)

    checkin = session.scalars(select(Checkin).where(Checkin.date == today)).first()
    if checkin is None:
        checkin = Checkin(date=today, applications_sent=applications_sent, note=note, reflection="")
        session.add(checkin)
    else:
        checkin.applications_sent = applications_sent
        checkin.note = note
    session.flush()

    plan = session.scalars(select(DailyPlan).where(DailyPlan.date == today)).first()
    tasks = [] if plan is None else list(plan.tasks)
    done_count = sum(1 for task in tasks if task.done)
    settings_row = progress_service.get_settings_row(session)
    goal_lines, _ = _goal_context_lines(session, today)

    context = (
        f"Today is {today.isoformat()}.\n"
        f"Tasks completed: {done_count} of {len(tasks)}.\n"
        f"Applications sent today: {applications_sent}"
        f" (floor: {settings_row.applications_floor}).\n"
        f"Owner's note: {note or 'none'}.\n"
        f"Goals:\n{goal_lines}"
    )
    prompt = load_prompt("evening_reflection_v1.txt").substitute(context=context)
    checkin.reflection = sanitize_copy(llm.complete_daily(prompt), REFLECTION_MAX_CHARS)
    session.flush()
    return checkin


def generate_retro(session: Session, llm: LlmClient, week_start: date) -> Retro:
    """Write the Sunday retro for the week starting Monday `week_start`."""
    week_end = week_start + timedelta(days=6)

    plans = session.scalars(
        select(DailyPlan)
        .where(DailyPlan.date >= week_start, DailyPlan.date <= week_end)
        .order_by(DailyPlan.date)
    ).all()
    checkins = session.scalars(
        select(Checkin)
        .where(Checkin.date >= week_start, Checkin.date <= week_end)
        .order_by(Checkin.date)
    ).all()

    day_lines: list[str] = []
    for plan in plans:
        tasks = list(plan.tasks)
        done = sum(1 for task in tasks if task.done)
        day_lines.append(f"- {plan.date.isoformat()}: {done} of {len(tasks)} planned tasks done")
    for checkin in checkins:
        note = f"; note: {checkin.note}" if checkin.note else ""
        day_lines.append(
            f"- {checkin.date.isoformat()}: {checkin.applications_sent} applications sent{note}"
        )
    if not day_lines:
        day_lines.append("- no plans or check-ins were logged this week")

    total_applications = sum(checkin.applications_sent for checkin in checkins)
    goal_lines, _ = _goal_context_lines(session, week_end)

    context = (
        f"Week of {week_start.isoformat()} to {week_end.isoformat()}.\n"
        f"Total applications sent this week: {total_applications}.\n"
        f"Days:\n{chr(10).join(day_lines)}\n"
        f"Goals with pace:\n{goal_lines}"
    )
    prompt = load_prompt("weekly_retro_v1.txt").substitute(context=context)
    body = sanitize_copy(llm.complete_retro(prompt), RETRO_MAX_CHARS)

    retro = session.scalars(select(Retro).where(Retro.week_start == week_start)).first()
    if retro is None:
        retro = Retro(week_start=week_start, body=body)
        session.add(retro)
    else:
        retro.body = body
    session.flush()
    return retro

from datetime import date

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.timeutil import user_today
from app.db import DbSession
from app.models import Goal, GoalLevel, GoalStatus, ProgressSource
from app.schemas import (
    ChildrenRollup,
    GoalCreate,
    GoalOut,
    GoalUpdate,
    PaceOut,
    ProgressAdd,
    ProgressEntryOut,
)
from app.services import progress as progress_service

router = APIRouter(tags=["goals"])


def _validate_period(period_start: date | None, period_end: date | None) -> None:
    if (period_start is None) != (period_end is None):
        raise HTTPException(422, "period_start and period_end must be set together")
    if period_start is not None and period_end is not None and period_end < period_start:
        raise HTTPException(422, "period_end must not be before period_start")


def _serialize_goal(session: Session, goal: Goal, today: date) -> GoalOut:
    current = progress_service.goal_current(session, goal.id)
    pace = progress_service.compute_pace(
        goal.target_value, current, goal.period_start, goal.period_end, today
    )
    children = [_serialize_goal(session, child, today) for child in goal.children]
    rollup: ChildrenRollup | None = None
    if goal.level == GoalLevel.BIG:
        counts = {"done": 0, "on_track": 0, "behind": 0}
        for child in children:
            if child.status == GoalStatus.DROPPED:
                continue
            if child.status == GoalStatus.DONE:
                counts["done"] += 1
            elif child.pace is not None and child.pace.status == "behind":
                counts["behind"] += 1
            else:
                counts["on_track"] += 1
        rollup = ChildrenRollup(**counts)
    return GoalOut(
        id=goal.id,
        level=goal.level,
        parent_id=goal.parent_id,
        title=goal.title,
        target_date=goal.target_date,
        status=goal.status,
        target_value=None if goal.target_value is None else float(goal.target_value),
        unit=goal.unit,
        auto_source=goal.auto_source,
        period_start=goal.period_start,
        period_end=goal.period_end,
        current=float(current),
        percent=progress_service.goal_percent(current, goal.target_value),
        pace=None if pace is None else PaceOut(expected=pace.expected, status=pace.status),
        last_activity=progress_service.last_activity(session, goal.id),
        tasks_done_7d=progress_service.tasks_done_last_7_days(session, goal.id, today),
        children=children,
        children_rollup=rollup,
    )


@router.get("/goals")
def list_goals(session: DbSession) -> list[GoalOut]:
    today = user_today()
    big_goals = session.scalars(
        select(Goal)
        .where(Goal.level == GoalLevel.BIG)
        .options(selectinload(Goal.children))
        .order_by(Goal.id)
    ).all()
    return [_serialize_goal(session, goal, today) for goal in big_goals]


@router.post("/goals", status_code=201)
def create_goal(payload: GoalCreate, session: DbSession) -> GoalOut:
    _validate_period(payload.period_start, payload.period_end)
    if payload.level == GoalLevel.BIG:
        if payload.parent_id is not None:
            raise HTTPException(422, "big goals cannot have a parent")
    else:
        if payload.parent_id is None:
            raise HTTPException(422, "monthly goals must be linked to a big goal")
        parent = session.get(Goal, payload.parent_id)
        if parent is None or parent.level != GoalLevel.BIG:
            raise HTTPException(422, "parent_id must reference an existing big goal")

    period_start, period_end = payload.period_start, payload.period_end
    if payload.target_value is not None and period_start is None:
        period_start, period_end = progress_service.month_bounds(user_today())

    goal = Goal(
        level=payload.level,
        parent_id=payload.parent_id,
        title=payload.title,
        target_date=payload.target_date,
        target_value=payload.target_value,
        unit=payload.unit,
        auto_source=payload.auto_source,
        period_start=period_start,
        period_end=period_end,
    )
    session.add(goal)
    session.commit()
    return _serialize_goal(session, goal, user_today())


@router.patch("/goals/{goal_id}")
def update_goal(goal_id: int, payload: GoalUpdate, session: DbSession) -> GoalOut:
    goal = session.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(404, "goal not found")

    fields = payload.model_dump(exclude_unset=True)
    for name, value in fields.items():
        setattr(goal, name, value)
    _validate_period(goal.period_start, goal.period_end)
    if goal.target_value is not None and goal.period_start is None:
        goal.period_start, goal.period_end = progress_service.month_bounds(user_today())
    session.commit()
    return _serialize_goal(session, goal, user_today())


@router.delete("/goals/{goal_id}", status_code=204)
def delete_goal(goal_id: int, session: DbSession) -> Response:
    goal = session.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(404, "goal not found")
    session.delete(goal)
    session.commit()
    return Response(status_code=204)


@router.post("/goals/{goal_id}/progress", status_code=201)
def add_manual_progress(
    goal_id: int, payload: ProgressAdd, session: DbSession
) -> dict[str, object]:
    goal = session.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(404, "goal not found")
    entry = progress_service.add_progress(
        session,
        goal,
        payload.delta,
        ProgressSource.MANUAL,
        day=user_today(),
        note=payload.note,
    )
    session.commit()
    return {
        "entry": ProgressEntryOut.model_validate(entry).model_dump(),
        "current": float(progress_service.goal_current(session, goal.id)),
    }

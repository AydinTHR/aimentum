from fastapi import APIRouter
from sqlalchemy import select

from app.core.timeutil import user_today
from app.db import DbSession
from app.models import Checkin, DailyPlan, Task
from app.schemas import CheckinOut, PlanOut, TaskOut, TodayOut

router = APIRouter(tags=["today"])


@router.get("/today")
def get_today(session: DbSession) -> TodayOut:
    today = user_today()
    plan = session.scalars(select(DailyPlan).where(DailyPlan.date == today)).first()
    checkin = session.scalars(select(Checkin).where(Checkin.date == today)).first()
    tasks: list[Task] = [] if plan is None else list(plan.tasks)
    return TodayOut(
        date=today,
        plan=None if plan is None else PlanOut.model_validate(plan),
        tasks=[TaskOut.model_validate(task) for task in tasks],
        checkin=None if checkin is None else CheckinOut.model_validate(checkin),
    )

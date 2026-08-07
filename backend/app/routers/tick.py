import secrets

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from app.core.config import settings
from app.core.timeutil import user_today
from app.db import DbSession, SessionFactoryDep
from app.schemas import TickOut
from app.services.jobs import JobName, claim_job, run_job
from app.services.llm import LlmDep
from app.services.push import PushDep

router = APIRouter(tags=["tick"])


@router.post("/tick", status_code=202)
def tick(
    job: JobName,
    background: BackgroundTasks,
    session: DbSession,
    factory: SessionFactoryDep,
    llm: LlmDep,
    transport: PushDep,
    x_tick_secret: str = Header(default=""),
) -> TickOut:
    """Run a scheduled job. Called by cron-job.org, not by the app.

    Returns 202 the moment the job is claimed and does the real work in a
    background task: Render's free tier is slow to wake and the caller's
    timeout is short, so anything slower than a claim risks the scheduler
    giving up and retrying against a job that is already running.

    Authenticated by its own secret header rather than the app's bearer
    token, and an unset TICK_SECRET fails closed.
    """
    if not settings.tick_secret or not secrets.compare_digest(x_tick_secret, settings.tick_secret):
        raise HTTPException(401, "invalid tick secret")

    today = user_today()
    claimed = claim_job(session, job, today)
    session.commit()

    if not claimed:
        return TickOut(job=job, date=today, status="already_ran")

    background.add_task(run_job, factory, transport, llm, job, today)
    return TickOut(job=job, date=today, status="scheduled")

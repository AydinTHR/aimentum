"""The four scheduled jobs behind /tick.

Every job is claimed in job_runs before it runs, so a cron retry or an
overlapping call sends exactly once per job per day. The claim happens in
the request, before the 202 goes back, because two calls arriving together
must not both get past it.

Push copy is assembled here from numbers the progress service produced, so
the evening notification carries the pace line on the lock screen and is
useful without opening the app.
"""

import enum
import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import SessionFactory
from app.models import DailyPlan, JobRun
from app.services import agent
from app.services.llm import LlmClient
from app.services.progress import format_number, pace_phrase, progress_summary
from app.services.push import Notification, PushTransport, send_to_all

logger = logging.getLogger(__name__)

MAX_GOALS_IN_PUSH = 2


class JobName(enum.StrEnum):
    MORNING = "morning"
    NUDGE = "nudge"
    EVENING = "evening"
    RETRO = "retro"


def claim_job(session: Session, job: JobName, day: date) -> bool:
    """Reserve this job for this day. False means it already ran.

    The unique constraint on (job, date) is what makes repeated ticks safe:
    the second insert loses the race and returns False rather than sending
    a duplicate notification.
    """
    session.add(JobRun(job=job.value, date=day))
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        return False
    return True


def week_start_for(day: date) -> date:
    """The Monday of the week containing `day`; the retro runs on Sunday."""
    return day - timedelta(days=day.weekday())


def morning_notification() -> Notification:
    return Notification(title="Plan your day", body="What are your top 3 today?")


def nudge_notification() -> Notification:
    return Notification(title="No plan yet", body="Take a minute and name your top 3.")


def evening_notification(session: Session, today: date) -> Notification:
    """Close the day, with the live pace line in the copy itself."""
    summary = progress_summary(session, today)
    floor = summary["applications_floor"]
    sent = summary["applications_sent_today"]
    goals = summary["goals"]

    parts: list[str] = []
    if isinstance(goals, list):
        for goal in goals[:MAX_GOALS_IN_PUSH]:
            pace = goal.get("pace")
            line = (
                f"{goal['title']}: {format_number(goal['current'])}"
                f" of {format_number(goal['target'])}"
            )
            if pace is not None:
                line += f", {pace_phrase(goal['current'], pace['expected'], pace['status'])}"
            parts.append(line)
    if not parts:
        applied = 0 if sent is None else sent
        parts.append(f"Applications today: {applied} of {floor}")

    return Notification(title="Close the day", body=". ".join(parts) + ".")


def retro_notification() -> Notification:
    return Notification(
        title="Your week in review",
        body="The retro is ready: what moved, what slipped, one adjustment.",
        url="/retros",
    )


def plan_exists(session: Session, day: date) -> bool:
    return session.scalars(select(DailyPlan).where(DailyPlan.date == day)).first() is not None


def dispatch(
    session: Session,
    transport: PushTransport,
    llm: LlmClient,
    job: JobName,
    day: date,
) -> None:
    """Do the job's work. The claim already happened in the request."""
    if job is JobName.MORNING:
        send_to_all(session, transport, job.value, morning_notification())
    elif job is JobName.NUDGE:
        if plan_exists(session, day):
            logger.info("nudge skipped: a plan already exists for %s", day)
            return
        send_to_all(session, transport, job.value, nudge_notification())
    elif job is JobName.EVENING:
        send_to_all(session, transport, job.value, evening_notification(session, day))
    else:
        agent.generate_retro(session, llm, week_start_for(day))
        send_to_all(session, transport, job.value, retro_notification())


def run_job(
    factory: SessionFactory,
    transport: PushTransport,
    llm: LlmClient,
    job: JobName,
    day: date,
) -> None:
    """Run a claimed job in its own session, after the 202 has been sent."""
    with factory() as session:
        try:
            dispatch(session, transport, llm, job, day)
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("job %s failed for %s", job.value, day)
            raise

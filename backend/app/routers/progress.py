from fastapi import APIRouter

from app.core.timeutil import user_today
from app.db import DbSession
from app.services.progress import progress_summary

router = APIRouter(tags=["progress"])


@router.get("/progress/summary")
def get_progress_summary(session: DbSession) -> dict[str, object]:
    summary = progress_summary(session, user_today())
    session.commit()
    return summary

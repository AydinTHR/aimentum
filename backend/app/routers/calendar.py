import logging

from fastapi import APIRouter

from app.core.timeutil import user_today
from app.schemas import CalendarDayOut, CalendarEventOut
from app.services.calendar import CalendarDep, CalendarUnavailable

logger = logging.getLogger(__name__)

router = APIRouter(tags=["calendar"])


@router.get("/calendar/today")
def calendar_today(calendar: CalendarDep) -> CalendarDayOut:
    """Read-only agenda for the Today screen.

    Reports availability rather than failing: the agenda strip is one part of
    a screen, and a calendar outage should not take the whole screen down.
    """
    today = user_today()
    try:
        events = calendar.list_events(today)
    except CalendarUnavailable as error:
        logger.warning("calendar unavailable: %s", error)
        return CalendarDayOut(date=today, available=False, events=[])
    return CalendarDayOut(
        date=today,
        available=True,
        events=[
            CalendarEventOut(
                summary=event.summary,
                start=event.start,
                end=event.end,
                all_day=event.all_day,
                calendar=event.calendar,
            )
            for event in events
        ],
    )

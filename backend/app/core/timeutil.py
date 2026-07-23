"""User-facing time handling.

All user-facing dates and times are America/Toronto; the database stores UTC.
Anything that needs "today" from the owner's point of view must go through
this module rather than calling date.today(), which uses the server clock.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

USER_TIMEZONE = ZoneInfo("America/Toronto")


def user_now() -> datetime:
    return datetime.now(tz=USER_TIMEZONE)


def user_today() -> date:
    return user_now().date()

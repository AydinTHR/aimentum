"""Find or create the dedicated calendar and print its id.

Run once, after scripts/google_oauth.py:

    uv run python scripts/google_calendar_setup.py

The agent writes time blocks only into this calendar, never into the
owner's own ones, so it can delete and rewrite its blocks freely on a
re-plan without touching anything a human put there.
"""

import sys

from app.core.config import settings
from app.services.calendar import CalendarUnavailable, GoogleCalendarService


def main() -> int:
    try:
        calendar_id = GoogleCalendarService().ensure_calendar()
    except CalendarUnavailable as error:
        print(f"Calendar setup failed: {error}", file=sys.stderr)
        return 1

    print(f"\nCalendar '{settings.gcal_calendar_name}' is ready.")
    print("\nPaste this into backend/.env:\n")
    print(f"GCAL_CALENDAR_ID={calendar_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

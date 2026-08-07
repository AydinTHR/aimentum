"""Google Calendar, behind a Protocol.

The agent reads real events so it can prioritize around them, and writes the
day's blocks into one dedicated calendar it owns, so Google's own apps stay
the calendar experience (ADR-0005). It never touches the owner's other
calendars except to read them.

Calendar is the one integration the product can lose without stopping: if
it is unreachable or unauthorized, planning still happens, just without
meetings. Every method raises CalendarUnavailable rather than a provider
specific error, so callers degrade on one exception type.
"""

import datetime as dt
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any, Protocol

from fastapi import Depends

from app.core.config import settings
from app.core.timeutil import USER_TIMEZONE

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_URI = "https://oauth2.googleapis.com/token"
# A personal account has a handful of calendars; the cap stops a pathological
# account from turning one agenda read into dozens of API calls.
MAX_CALENDARS = 12


class CalendarUnavailable(Exception):
    """Calendar could not be reached or is not configured. Degrade, do not fail."""


@dataclass(frozen=True)
class CalendarEvent:
    """One event, already normalized to the owner's timezone."""

    id: str
    summary: str
    start: dt.datetime
    end: dt.datetime
    all_day: bool = False
    calendar: str = ""

    @property
    def blocks_time(self) -> bool:
        """Whether this event should stop a task being scheduled over it.

        All-day entries are usually birthdays, holidays, or reminders rather
        than commitments that consume the working day, so they show in the
        agenda but do not reserve time.
        """
        return not self.all_day


class CalendarService(Protocol):
    def list_events(self, day: dt.date) -> list[CalendarEvent]: ...

    def create_block(self, summary: str, start: dt.datetime, minutes: int) -> str: ...

    def delete_block(self, event_id: str) -> None: ...

    def ensure_calendar(self) -> str: ...


def _day_bounds(day: dt.date) -> tuple[dt.datetime, dt.datetime]:
    start = dt.datetime.combine(day, dt.time.min, tzinfo=USER_TIMEZONE)
    return start, start + dt.timedelta(days=1)


class GoogleCalendarService:
    """Google Calendar v3 using the owner's own refresh token.

    Auth is a one-time authorization done with scripts/google_oauth.py; there
    is no user-facing OAuth flow in this product. The client is built lazily
    so importing this module never needs credentials.
    """

    def __init__(self) -> None:
        self._service: Any | None = None

    def _client(self) -> Any:
        if self._service is not None:
            return self._service
        if not settings.google_oauth_refresh_token:
            raise CalendarUnavailable("GOOGLE_OAUTH_REFRESH_TOKEN is not set")
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            credentials = Credentials(  # type: ignore[no-untyped-call]
                token=None,
                refresh_token=settings.google_oauth_refresh_token,
                client_id=settings.google_oauth_client_id,
                client_secret=settings.google_oauth_client_secret,
                token_uri=TOKEN_URI,
                scopes=SCOPES,
            )
            self._service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        except CalendarUnavailable:
            raise
        except Exception as error:
            raise CalendarUnavailable(f"could not build calendar client: {error}") from error
        return self._service

    @staticmethod
    def _parse_event(raw: dict[str, Any], calendar_name: str) -> CalendarEvent | None:
        start_raw, end_raw = raw.get("start", {}), raw.get("end", {})
        if "dateTime" in start_raw:
            start = dt.datetime.fromisoformat(start_raw["dateTime"]).astimezone(USER_TIMEZONE)
            end = dt.datetime.fromisoformat(end_raw["dateTime"]).astimezone(USER_TIMEZONE)
            all_day = False
        elif "date" in start_raw:
            start = dt.datetime.combine(
                dt.date.fromisoformat(start_raw["date"]), dt.time.min, tzinfo=USER_TIMEZONE
            )
            end = dt.datetime.combine(
                dt.date.fromisoformat(end_raw["date"]), dt.time.min, tzinfo=USER_TIMEZONE
            )
            all_day = True
        else:
            return None
        return CalendarEvent(
            id=raw.get("id", ""),
            summary=raw.get("summary") or "(no title)",
            start=start,
            end=end,
            all_day=all_day,
            calendar=calendar_name,
        )

    def list_events(self, day: dt.date) -> list[CalendarEvent]:
        """Every event on `day` across the owner's calendars, in local time."""
        service = self._client()
        time_min, time_max = _day_bounds(day)
        try:
            entries = service.calendarList().list(maxResults=MAX_CALENDARS).execute()
            events: list[CalendarEvent] = []
            for entry in entries.get("items", []):
                if entry.get("selected") is False:
                    continue
                raw_events = (
                    service.events()
                    .list(
                        calendarId=entry["id"],
                        timeMin=time_min.isoformat(),
                        timeMax=time_max.isoformat(),
                        singleEvents=True,
                        orderBy="startTime",
                    )
                    .execute()
                )
                for raw in raw_events.get("items", []):
                    if raw.get("status") == "cancelled":
                        continue
                    parsed = self._parse_event(raw, entry.get("summary", ""))
                    if parsed is not None:
                        events.append(parsed)
        except Exception as error:
            raise CalendarUnavailable(f"could not read events: {error}") from error
        return sorted(events, key=lambda event: (event.all_day, event.start))

    def create_block(self, summary: str, start: dt.datetime, minutes: int) -> str:
        service = self._client()
        calendar_id = settings.gcal_calendar_id or self.ensure_calendar()
        body = {
            "summary": summary,
            "start": {"dateTime": start.isoformat(), "timeZone": str(USER_TIMEZONE)},
            "end": {
                "dateTime": (start + dt.timedelta(minutes=minutes)).isoformat(),
                "timeZone": str(USER_TIMEZONE),
            },
        }
        try:
            created = service.events().insert(calendarId=calendar_id, body=body).execute()
        except Exception as error:
            raise CalendarUnavailable(f"could not create block: {error}") from error
        return str(created["id"])

    def delete_block(self, event_id: str) -> None:
        service = self._client()
        calendar_id = settings.gcal_calendar_id or self.ensure_calendar()
        try:
            service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        except Exception as error:
            # A block the owner already deleted in Google's UI is not an error
            # worth failing a re-plan over.
            logger.info("could not delete calendar block %s: %s", event_id, error)

    def ensure_calendar(self) -> str:
        """Find the dedicated calendar by name, creating it the first time."""
        service = self._client()
        name = settings.gcal_calendar_name
        try:
            entries = service.calendarList().list(maxResults=MAX_CALENDARS).execute()
            for entry in entries.get("items", []):
                if entry.get("summary") == name:
                    return str(entry["id"])
            created = (
                service.calendars()
                .insert(body={"summary": name, "timeZone": str(USER_TIMEZONE)})
                .execute()
            )
        except Exception as error:
            raise CalendarUnavailable(f"could not resolve the calendar: {error}") from error
        return str(created["id"])


class FakeCalendarService:
    """In-memory calendar for tests. Records every write."""

    def __init__(self, events: list[CalendarEvent] | None = None) -> None:
        self.events = list(events or [])
        self.created: list[tuple[str, dt.datetime, int]] = []
        self.deleted: list[str] = []
        self.available = True
        self._next_id = 1

    def _check(self) -> None:
        if not self.available:
            raise CalendarUnavailable("fake calendar is offline")

    def list_events(self, day: dt.date) -> list[CalendarEvent]:
        self._check()
        return [event for event in self.events if event.start.date() == day]

    def create_block(self, summary: str, start: dt.datetime, minutes: int) -> str:
        self._check()
        self.created.append((summary, start, minutes))
        event_id = f"fake-event-{self._next_id}"
        self._next_id += 1
        return event_id

    def delete_block(self, event_id: str) -> None:
        self._check()
        self.deleted.append(event_id)

    def ensure_calendar(self) -> str:
        self._check()
        return "fake-calendar-id"


@lru_cache(maxsize=1)
def get_calendar() -> CalendarService:
    return GoogleCalendarService()


CalendarDep = Annotated[CalendarService, Depends(get_calendar)]

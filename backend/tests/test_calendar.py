import datetime as dt
import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.timeutil import USER_TIMEZONE, user_today
from app.models import Task
from app.services.calendar import CalendarEvent, FakeCalendarService
from tests.agent_fakes import FakeLlm


def at(hour: int, minute: int = 0, day: dt.date | None = None) -> dt.datetime:
    day = day or user_today()
    return dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=USER_TIMEZONE)


def meeting(summary: str, start_hour: int, end_hour: int) -> CalendarEvent:
    return CalendarEvent(
        id=f"evt-{summary}", summary=summary, start=at(start_hour), end=at(end_hour)
    )


def plan_with_blocks(client: TestClient, fake_llm: FakeLlm, tasks: list[dict]) -> dict:
    fake_llm.queue_daily(json.dumps({"tasks": tasks, "rationale": "Applications first."}))
    response = client.post(
        "/checkin/morning", json={"raw_text": "apply, gym, groceries", "input_mode": "text"}
    )
    assert response.status_code == 200
    return dict(response.json())


class TestAgendaEndpoint:
    def test_returns_todays_events(
        self, client: TestClient, fake_calendar: FakeCalendarService
    ) -> None:
        fake_calendar.events = [meeting("Standup", 9, 10), meeting("1:1", 14, 15)]

        payload = client.get("/calendar/today").json()

        assert payload["available"] is True
        assert [event["summary"] for event in payload["events"]] == ["Standup", "1:1"]
        assert payload["events"][0]["start"].startswith(user_today().isoformat())

    def test_reports_unavailable_rather_than_failing(
        self, client: TestClient, fake_calendar: FakeCalendarService
    ) -> None:
        """The agenda is one strip on a screen; an outage must not 500 it."""
        fake_calendar.available = False

        response = client.get("/calendar/today")

        assert response.status_code == 200
        assert response.json() == {
            "date": user_today().isoformat(),
            "available": False,
            "events": [],
        }

    def test_empty_calendar_is_available_and_empty(self, client: TestClient) -> None:
        payload = client.get("/calendar/today").json()
        assert payload["available"] is True
        assert payload["events"] == []


class TestEventsReachThePrompt:
    def test_meetings_are_listed_for_claude(
        self, client: TestClient, fake_calendar: FakeCalendarService, fake_llm: FakeLlm
    ) -> None:
        fake_calendar.events = [meeting("Standup", 9, 10)]
        plan_with_blocks(client, fake_llm, [{"title": "Apply"}])

        prompt = fake_llm.daily_prompts[0]
        assert "09:00 to 10:00: Standup" in prompt
        assert "Workday window: 09:00 to 18:00" in prompt

    def test_an_empty_day_says_so(self, client: TestClient, fake_llm: FakeLlm) -> None:
        plan_with_blocks(client, fake_llm, [{"title": "Apply"}])
        assert "nothing scheduled" in fake_llm.daily_prompts[0]


class TestWritingBlocks:
    def test_blocks_are_written_and_stored(
        self,
        client: TestClient,
        db_session: Session,
        fake_calendar: FakeCalendarService,
        fake_llm: FakeLlm,
    ) -> None:
        payload = plan_with_blocks(
            client,
            fake_llm,
            [
                {"title": "Apply to 5 roles", "block_start": "10:00", "block_minutes": 90},
                {"title": "Gym", "block_start": "16:00", "block_minutes": 60},
            ],
        )

        assert [summary for summary, _, _ in fake_calendar.created] == [
            "Apply to 5 roles",
            "Gym",
        ]
        assert [minutes for _, _, minutes in fake_calendar.created] == [90, 60]

        tasks = payload["tasks"]
        assert tasks[0]["block_minutes"] == 90
        assert tasks[0]["gcal_event_id"] == "fake-event-1"
        assert tasks[1]["gcal_event_id"] == "fake-event-2"

        # The wall-clock time the owner asked for, not the database's UTC.
        returned = dt.datetime.fromisoformat(tasks[0]["block_start"])
        assert returned == at(10)
        assert returned.strftime("%H:%M") == "10:00"
        assert returned.date() == user_today()

        stored = db_session.query(Task).order_by(Task.sort).all()
        assert [task.gcal_event_id for task in stored] == ["fake-event-1", "fake-event-2"]

    def test_a_block_over_a_meeting_is_not_written(
        self, client: TestClient, fake_calendar: FakeCalendarService, fake_llm: FakeLlm
    ) -> None:
        """The whole point of validating in code rather than in the prompt."""
        fake_calendar.events = [meeting("Standup", 10, 11)]

        payload = plan_with_blocks(
            client,
            fake_llm,
            [
                {"title": "Apply", "block_start": "10:00", "block_minutes": 60},
                {"title": "Gym", "block_start": "14:00", "block_minutes": 60},
            ],
        )

        assert [summary for summary, _, _ in fake_calendar.created] == ["Gym"]
        assert payload["tasks"][0]["gcal_event_id"] is None
        assert payload["tasks"][0]["block_start"] is None
        assert payload["tasks"][1]["gcal_event_id"] == "fake-event-1"

    def test_a_late_block_keeps_todays_date(
        self, client: TestClient, fake_calendar: FakeCalendarService, fake_llm: FakeLlm
    ) -> None:
        """In UTC a 20:30 block falls on tomorrow; the payload must not."""
        client.patch("/settings", json={"workday_end": "23:00:00"})

        payload = plan_with_blocks(
            client,
            fake_llm,
            [{"title": "Late review", "block_start": "20:30", "block_minutes": 45}],
        )

        returned = dt.datetime.fromisoformat(payload["tasks"][0]["block_start"])
        assert returned.strftime("%H:%M") == "20:30"
        assert returned.date() == user_today()

    def test_tasks_without_a_proposal_get_no_block(
        self, client: TestClient, fake_calendar: FakeCalendarService, fake_llm: FakeLlm
    ) -> None:
        payload = plan_with_blocks(
            client, fake_llm, [{"title": "Apply", "block_start": None, "block_minutes": None}]
        )
        assert fake_calendar.created == []
        assert payload["tasks"][0]["block_start"] is None

    def test_a_malformed_block_time_is_ignored_not_fatal(
        self, client: TestClient, fake_calendar: FakeCalendarService, fake_llm: FakeLlm
    ) -> None:
        payload = plan_with_blocks(
            client,
            fake_llm,
            [{"title": "Apply", "block_start": "tomorrow morning", "block_minutes": 60}],
        )
        assert fake_calendar.created == []
        assert payload["tasks"][0]["title"] == "Apply"

    def test_blocking_disabled_in_settings_writes_nothing(
        self, client: TestClient, fake_calendar: FakeCalendarService, fake_llm: FakeLlm
    ) -> None:
        client.patch("/settings", json={"time_blocking_enabled": False})

        plan_with_blocks(
            client, fake_llm, [{"title": "Apply", "block_start": "10:00", "block_minutes": 60}]
        )

        assert fake_calendar.created == []
        assert "disabled today" in fake_llm.daily_prompts[0]


class TestReplan:
    def test_replanning_deletes_the_previous_blocks(
        self, client: TestClient, fake_calendar: FakeCalendarService, fake_llm: FakeLlm
    ) -> None:
        plan_with_blocks(
            client, fake_llm, [{"title": "Old", "block_start": "10:00", "block_minutes": 60}]
        )
        assert fake_calendar.created == [("Old", at(10), 60)]

        payload = plan_with_blocks(
            client, fake_llm, [{"title": "New", "block_start": "11:00", "block_minutes": 30}]
        )

        assert fake_calendar.deleted == ["fake-event-1"]
        assert [summary for summary, _, _ in fake_calendar.created] == ["Old", "New"]
        assert payload["tasks"][0]["gcal_event_id"] == "fake-event-2"


class TestGracefulDegradation:
    def test_planning_still_works_when_the_calendar_is_down(
        self, client: TestClient, fake_calendar: FakeCalendarService, fake_llm: FakeLlm
    ) -> None:
        fake_calendar.available = False

        payload = plan_with_blocks(
            client, fake_llm, [{"title": "Apply", "block_start": "10:00", "block_minutes": 60}]
        )

        assert [task["title"] for task in payload["tasks"]] == ["Apply"]
        assert payload["tasks"][0]["block_start"] is None
        assert fake_calendar.created == []

    def test_the_rationale_admits_the_calendar_was_missing(
        self, client: TestClient, fake_calendar: FakeCalendarService, fake_llm: FakeLlm
    ) -> None:
        fake_calendar.available = False

        payload = plan_with_blocks(client, fake_llm, [{"title": "Apply"}])

        assert "Calendar was unreachable" in payload["plan"]["rationale"]

    def test_the_prompt_says_the_calendar_is_unavailable(
        self, client: TestClient, fake_calendar: FakeCalendarService, fake_llm: FakeLlm
    ) -> None:
        fake_calendar.available = False
        plan_with_blocks(client, fake_llm, [{"title": "Apply"}])
        assert "unavailable" in fake_llm.daily_prompts[0]

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.timeutil import user_today
from app.models import Checkin, DailyPlan, Goal, GoalLevel, InputMode, Task
from app.services.progress import month_bounds, record_applications


class TestToday:
    def test_empty_day(self, client: TestClient) -> None:
        payload = client.get("/today").json()
        assert payload["date"] == user_today().isoformat()
        assert payload["plan"] is None
        assert payload["tasks"] == []
        assert payload["checkin"] is None

    def test_populated_day(self, client: TestClient, db_session: Session) -> None:
        today = user_today()
        plan = DailyPlan(
            date=today,
            raw_input="apply, gym, groceries",
            input_mode=InputMode.TEXT,
            rationale="Applications first: floor not covered yet.",
        )
        db_session.add(plan)
        db_session.flush()
        db_session.add_all(
            [
                Task(plan_id=plan.id, title="Send 5 applications", sort=0),
                Task(plan_id=plan.id, title="Gym", sort=1, done=True),
            ]
        )
        db_session.add(Checkin(date=today, applications_sent=6, note="solid", reflection="ok"))
        db_session.commit()

        payload = client.get("/today").json()
        assert payload["plan"]["raw_input"] == "apply, gym, groceries"
        assert payload["plan"]["rationale"].startswith("Applications first")
        assert [task["title"] for task in payload["tasks"]] == ["Send 5 applications", "Gym"]
        assert payload["tasks"][1]["done"] is True
        assert payload["checkin"]["applications_sent"] == 6


class TestSettings:
    def test_defaults_are_created_on_first_read(self, client: TestClient) -> None:
        payload = client.get("/settings").json()
        assert payload == {
            "applications_floor": 5,
            "read_back_enabled": False,
            "time_blocking_enabled": True,
            "workday_start": "09:00:00",
            "workday_end": "18:00:00",
        }

    def test_patch_persists(self, client: TestClient) -> None:
        response = client.patch(
            "/settings", json={"applications_floor": 7, "read_back_enabled": True}
        )
        assert response.status_code == 200
        payload = client.get("/settings").json()
        assert payload["applications_floor"] == 7
        assert payload["read_back_enabled"] is True
        assert payload["time_blocking_enabled"] is True


class TestProgressSummary:
    def test_empty_summary(self, client: TestClient) -> None:
        payload = client.get("/progress/summary").json()
        assert payload["date"] == user_today().isoformat()
        assert payload["applications_floor"] == 5
        assert payload["applications_sent_today"] is None
        assert payload["goals"] == []

    def test_summary_carries_bars_and_pace(self, client: TestClient, db_session: Session) -> None:
        today = user_today()
        start, end = month_bounds(today)
        big = Goal(level=GoalLevel.BIG, title="Job search")
        db_session.add(big)
        db_session.flush()
        monthly = Goal(
            level=GoalLevel.MONTHLY,
            parent_id=big.id,
            title="Applications",
            auto_source="applications",
            target_value=Decimal(40),
            unit="applications",
            period_start=start,
            period_end=end,
        )
        db_session.add(monthly)
        db_session.flush()
        record_applications(db_session, today, 6)
        db_session.add(Checkin(date=today, applications_sent=6, reflection="ok"))
        db_session.commit()

        payload = client.get("/progress/summary").json()
        assert payload["applications_sent_today"] == 6
        assert len(payload["goals"]) == 1
        goal_payload = payload["goals"][0]
        assert goal_payload["title"] == "Applications"
        assert goal_payload["current"] == 6.0
        assert goal_payload["target"] == 40.0
        assert goal_payload["percent"] == 15.0
        assert goal_payload["pace"] is not None
        assert goal_payload["pace"]["status"] in {"ahead", "on_track", "behind"}

    def test_non_metric_goals_stay_out_of_the_summary(
        self, client: TestClient, db_session: Session
    ) -> None:
        big = Goal(level=GoalLevel.BIG, title="Job search")
        db_session.add(big)
        db_session.flush()
        db_session.add(
            Goal(level=GoalLevel.MONTHLY, parent_id=big.id, title="Vague improvement goal")
        )
        db_session.commit()
        assert client.get("/progress/summary").json()["goals"] == []


def test_checkin_date_uniqueness_is_enforced(db_session: Session) -> None:
    day = date(2026, 7, 23)
    db_session.add(Checkin(date=day, applications_sent=1, reflection="a"))
    db_session.commit()
    db_session.add(Checkin(date=day, applications_sent=2, reflection="b"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

import json
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import user_today
from app.models import JobRun, PushLog, Retro
from app.services.jobs import week_start_for
from app.services.push import FakePushTransport
from tests.agent_fakes import FakeLlm
from tests.conftest import TEST_TICK_SECRET
from tests.test_agent_morning import make_goals, morning
from tests.test_push import subscribe

SECRET_HEADER = {"X-Tick-Secret": TEST_TICK_SECRET}


def tick(client: TestClient, job: str, secret: str | None = TEST_TICK_SECRET) -> object:
    headers = {} if secret is None else {"X-Tick-Secret": secret}
    return client.post(f"/tick?job={job}", headers=headers)


class TestTickAuth:
    def test_missing_secret_is_rejected(self, client: TestClient) -> None:
        assert tick(client, "morning", secret=None).status_code == 401

    def test_wrong_secret_is_rejected(self, client: TestClient) -> None:
        assert tick(client, "morning", secret="nope").status_code == 401

    def test_unset_server_secret_fails_closed(self, client: TestClient, monkeypatch) -> None:
        from app.core.config import settings

        monkeypatch.setattr(settings, "tick_secret", "")
        assert tick(client, "morning", secret="").status_code == 401

    def test_tick_does_not_need_the_bearer_token(
        self, client: TestClient, fake_push: FakePushTransport
    ) -> None:
        """cron-job.org only carries the tick secret, never the app token."""
        response = client.post(
            "/tick?job=morning",
            headers={"X-Tick-Secret": TEST_TICK_SECRET, "Authorization": "Bearer wrong"},
        )
        assert response.status_code == 202

    def test_unknown_job_is_rejected(self, client: TestClient) -> None:
        assert tick(client, "brunch").status_code == 422


class TestIdempotency:
    def test_repeated_ticks_send_exactly_once(
        self, client: TestClient, db_session: Session, fake_push: FakePushTransport
    ) -> None:
        subscribe(client)

        first = tick(client, "morning")
        assert first.status_code == 202
        assert first.json()["status"] == "scheduled"

        for _ in range(3):
            repeat = tick(client, "morning")
            assert repeat.status_code == 202
            assert repeat.json()["status"] == "already_ran"

        assert len(fake_push.sent) == 1
        assert db_session.query(PushLog).count() == 1
        assert db_session.scalars(select(JobRun)).one().job == "morning"

    def test_different_jobs_on_the_same_day_both_run(
        self, client: TestClient, db_session: Session, fake_push: FakePushTransport
    ) -> None:
        subscribe(client)
        assert tick(client, "morning").json()["status"] == "scheduled"
        assert tick(client, "evening").json()["status"] == "scheduled"

        assert len(fake_push.sent) == 2
        jobs = db_session.scalars(select(JobRun.job).order_by(JobRun.id)).all()
        assert sorted(jobs) == ["evening", "morning"]

    def test_a_claimed_job_stays_claimed_even_with_no_subscriptions(
        self, client: TestClient, db_session: Session, fake_push: FakePushTransport
    ) -> None:
        assert tick(client, "morning").json()["status"] == "scheduled"
        assert tick(client, "morning").json()["status"] == "already_ran"
        assert fake_push.sent == []


class TestJobBehavior:
    def test_morning_push_copy(self, client: TestClient, fake_push: FakePushTransport) -> None:
        subscribe(client)
        tick(client, "morning")

        body = json.loads(fake_push.sent[0][1])
        assert body["title"] == "Plan your day"
        assert body["url"] == "/today"

    def test_nudge_sends_when_no_plan_exists(
        self, client: TestClient, fake_push: FakePushTransport
    ) -> None:
        subscribe(client)
        tick(client, "nudge")

        assert len(fake_push.sent) == 1
        assert json.loads(fake_push.sent[0][1])["title"] == "No plan yet"

    def test_nudge_skips_when_the_plan_already_exists(
        self,
        client: TestClient,
        db_session: Session,
        fake_push: FakePushTransport,
        fake_llm: FakeLlm,
    ) -> None:
        subscribe(client)
        fake_llm.queue_daily(json.dumps({"tasks": [{"title": "Apply"}], "rationale": "r"}))
        morning(client)

        response = tick(client, "nudge")
        assert response.json()["status"] == "scheduled"
        assert fake_push.sent == []
        assert db_session.query(PushLog).count() == 0
        # The job is still recorded, so it does not retry all morning.
        assert db_session.scalars(select(JobRun)).one().job == "nudge"

    def test_evening_copy_carries_the_pace_line(
        self, client: TestClient, fake_push: FakePushTransport, fake_llm: FakeLlm
    ) -> None:
        make_goals(client)
        subscribe(client)
        fake_llm.queue_daily("Solid day.")
        client.post("/checkin/evening", json={"applications_sent": 6, "task_states": []})

        tick(client, "evening")
        body = json.loads(fake_push.sent[0][1])

        assert body["title"] == "Close the day"
        assert "40 quality applications: 6 of 40" in body["body"]
        assert "pace" in body["body"] or "on track" in body["body"]

    def test_evening_copy_without_metric_goals_falls_back_to_the_floor(
        self, client: TestClient, fake_push: FakePushTransport
    ) -> None:
        subscribe(client)
        tick(client, "evening")

        body = json.loads(fake_push.sent[0][1])
        assert body["body"] == "Applications today: 0 of 5."

    def test_retro_job_generates_the_retro_and_pushes(
        self,
        client: TestClient,
        db_session: Session,
        fake_push: FakePushTransport,
        fake_llm: FakeLlm,
    ) -> None:
        subscribe(client)
        fake_llm.queue_retro("Applications moved. Sleep slipped. Block mornings next week.")

        tick(client, "retro")

        retro = db_session.scalars(select(Retro)).one()
        assert retro.week_start == week_start_for(user_today())
        assert retro.body.startswith("Applications moved.")

        body = json.loads(fake_push.sent[0][1])
        assert body["url"] == "/retros"

    def test_push_log_records_the_job_name(
        self, client: TestClient, db_session: Session, fake_push: FakePushTransport
    ) -> None:
        subscribe(client)
        tick(client, "morning")
        assert db_session.scalars(select(PushLog)).one().job == "morning"


class TestWeekStart:
    def test_sunday_resolves_to_that_weeks_monday(self) -> None:
        assert week_start_for(date(2026, 8, 9)) == date(2026, 8, 3)

    def test_monday_resolves_to_itself(self) -> None:
        assert week_start_for(date(2026, 8, 3)) == date(2026, 8, 3)

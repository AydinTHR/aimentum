from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Checkin, DailyPlan, InputMode, Task
from app.services.agent import generate_retro
from tests.agent_fakes import FakeLlm

WEEK_START = date(2026, 7, 27)  # a Monday


def seed_week(session: Session) -> None:
    for offset, (done, total, apps) in enumerate([(3, 3, 6), (1, 2, 4), (2, 3, 5)]):
        day = WEEK_START + timedelta(days=offset)
        plan = DailyPlan(date=day, raw_input="plan", input_mode=InputMode.TEXT)
        session.add(plan)
        session.flush()
        for i in range(total):
            session.add(Task(plan_id=plan.id, title=f"task {i}", sort=i, done=i < done))
        session.add(
            Checkin(
                date=day, applications_sent=apps, reflection="r", note="n" if offset == 0 else None
            )
        )
    session.commit()


class TestWeeklyRetro:
    def test_generates_and_stores_the_retro(self, db_session: Session, fake_llm: FakeLlm) -> None:
        seed_week(db_session)
        fake_llm.queue_retro("Applications moved. The gym slipped. Next week, block mornings.")
        retro = generate_retro(db_session, fake_llm, WEEK_START)
        db_session.commit()

        assert retro.week_start == WEEK_START
        assert retro.body.startswith("Applications moved.")
        prompt = fake_llm.retro_prompts[0]
        assert "Total applications sent this week: 15" in prompt
        assert "2026-07-27: 3 of 3 planned tasks done" in prompt
        assert "2026-07-28: 4 applications sent" in prompt

    def test_retro_is_capped_and_sanitized(self, db_session: Session, fake_llm: FakeLlm) -> None:
        fake_llm.queue_retro("A \u2014 B. " + "y" * 2000)
        retro = generate_retro(db_session, fake_llm, WEEK_START)
        assert len(retro.body) <= 1200
        assert "\u2014" not in retro.body

    def test_regenerating_the_same_week_updates_in_place(
        self, db_session: Session, fake_llm: FakeLlm
    ) -> None:
        fake_llm.queue_retro("first")
        generate_retro(db_session, fake_llm, WEEK_START)
        fake_llm.queue_retro("second")
        retro = generate_retro(db_session, fake_llm, WEEK_START)
        db_session.commit()

        assert retro.body == "second"
        from app.models import Retro

        assert db_session.query(Retro).count() == 1

    def test_retro_endpoints(
        self, client: TestClient, db_session: Session, fake_llm: FakeLlm
    ) -> None:
        assert client.get("/retros/latest").status_code == 404
        assert client.get("/retros").json() == []

        fake_llm.queue_retro("week one")
        generate_retro(db_session, fake_llm, WEEK_START)
        fake_llm.queue_retro("week two")
        generate_retro(db_session, fake_llm, WEEK_START + timedelta(days=7))
        db_session.commit()

        retros = client.get("/retros").json()
        assert [r["body"] for r in retros] == ["week two", "week one"]
        assert client.get("/retros/latest").json()["body"] == "week two"

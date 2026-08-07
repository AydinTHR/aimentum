import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Goal
from app.services.progress import goal_current
from tests.agent_fakes import FakeLlm
from tests.test_agent_morning import make_goals, morning


def evening(
    client: TestClient,
    applications: int,
    task_states: list[dict] | None = None,
    note: str | None = None,
) -> dict:
    response = client.post(
        "/checkin/evening",
        json={
            "applications_sent": applications,
            "note": note,
            "task_states": task_states or [],
        },
    )
    assert response.status_code == 200
    return dict(response.json())


class TestEveningCheckin:
    def test_saves_checkin_with_reflection_and_logs_applications(
        self, client: TestClient, fake_llm: FakeLlm, db_session: Session
    ) -> None:
        goal_id = make_goals(client)
        fake_llm.queue_daily(
            json.dumps({"tasks": [{"title": "Apply"}, {"title": "Gym"}], "rationale": "r"})
        )
        plan = morning(client)
        task_ids = [task["id"] for task in plan["tasks"]]

        fake_llm.queue_daily("Six applications, one over the floor. Solid day.")
        payload = evening(
            client,
            applications=6,
            task_states=[{"id": task_ids[0], "done": True}],
            note="felt good",
        )

        assert payload["checkin"]["applications_sent"] == 6
        assert payload["checkin"]["reflection"].startswith("Six applications")
        assert goal_current(db_session, goal_id) == 6
        summary_goals = payload["summary"]["goals"]
        assert summary_goals[0]["current"] == 6.0

        today = client.get("/today").json()
        done_flags = {task["id"]: task["done"] for task in today["tasks"]}
        assert done_flags[task_ids[0]] is True
        assert done_flags[task_ids[1]] is False

    def test_editing_a_checkin_resets_the_count_and_reflection(
        self, client: TestClient, fake_llm: FakeLlm, db_session: Session
    ) -> None:
        goal_id = make_goals(client)
        fake_llm.queue_daily("First reflection.")
        evening(client, applications=5)
        fake_llm.queue_daily("Corrected reflection.")
        payload = evening(client, applications=8)

        assert payload["checkin"]["applications_sent"] == 8
        assert payload["checkin"]["reflection"] == "Corrected reflection."
        assert goal_current(db_session, goal_id) == 8

    def test_reflection_prompt_cites_the_real_numbers(
        self, client: TestClient, fake_llm: FakeLlm
    ) -> None:
        make_goals(client)
        fake_llm.queue_daily("ok")
        evening(client, applications=3, note="tough day")

        prompt = fake_llm.daily_prompts[-1]
        assert "Applications sent today: 3" in prompt
        assert "floor: 5" in prompt
        assert "tough day" in prompt
        assert "3 of 40" in prompt

    def test_reflection_is_capped_and_sanitized(
        self, client: TestClient, fake_llm: FakeLlm
    ) -> None:
        fake_llm.queue_daily("Great work \u2014 keep it up! " + "x" * 600)
        payload = evening(client, applications=5)

        reflection = payload["checkin"]["reflection"]
        assert len(reflection) <= 400
        assert "\u2014" not in reflection

    def test_task_completion_feeds_tasks_done_goals(
        self, client: TestClient, fake_llm: FakeLlm, db_session: Session
    ) -> None:
        big = client.post("/goals", json={"level": "big", "title": "Health"}).json()
        goal = client.post(
            "/goals",
            json={
                "level": "monthly",
                "parent_id": big["id"],
                "title": "20 workouts",
                "target_value": 20,
                "auto_source": "tasks_done",
            },
        ).json()
        fake_llm.queue_daily(
            json.dumps(
                {"tasks": [{"title": "Gym", "monthly_goal_id": goal["id"]}], "rationale": "r"}
            )
        )
        plan = morning(client, text="gym")
        fake_llm.queue_daily("ok")
        evening(client, applications=0, task_states=[{"id": plan["tasks"][0]["id"], "done": True}])

        assert goal_current(db_session, goal["id"]) == 1
        assert db_session.query(Goal).count() == 2

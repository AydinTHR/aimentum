import json

from fastapi.testclient import TestClient

from app.core.timeutil import user_today
from tests.agent_fakes import FakeLlm


def make_goals(client: TestClient) -> int:
    big = client.post("/goals", json={"level": "big", "title": "Job search"}).json()
    monthly = client.post(
        "/goals",
        json={
            "level": "monthly",
            "parent_id": big["id"],
            "title": "40 quality applications",
            "target_value": 40,
            "unit": "applications",
            "auto_source": "applications",
        },
    ).json()
    return int(monthly["id"])


def morning(client: TestClient, text: str = "apply to 5 jobs, gym, call mom") -> dict:
    response = client.post("/checkin/morning", json={"raw_text": text, "input_mode": "text"})
    assert response.status_code == 200
    return dict(response.json())


class TestMorningParseAndPrioritize:
    def test_happy_path_creates_ordered_linked_tasks(
        self, client: TestClient, fake_llm: FakeLlm
    ) -> None:
        goal_id = make_goals(client)
        fake_llm.queue_daily(
            json.dumps(
                {
                    "tasks": [
                        {"title": "Apply to 5 jobs", "monthly_goal_id": goal_id},
                        {"title": "Gym", "monthly_goal_id": None},
                        {"title": "Call mom", "monthly_goal_id": None},
                    ],
                    "rationale": "Applications first because the floor is not covered.",
                }
            )
        )
        payload = morning(client)

        titles = [task["title"] for task in payload["tasks"]]
        assert titles == ["Apply to 5 jobs", "Gym", "Call mom"]
        assert [task["sort"] for task in payload["tasks"]] == [0, 1, 2]
        assert payload["tasks"][0]["monthly_goal_id"] == goal_id
        assert payload["plan"]["rationale"].startswith("Applications first")

        today = client.get("/today").json()
        assert len(today["tasks"]) == 3

    def test_prompt_carries_pace_numbers_and_raw_text(
        self, client: TestClient, fake_llm: FakeLlm
    ) -> None:
        make_goals(client)
        fake_llm.queue_daily(json.dumps({"tasks": [{"title": "x"}], "rationale": "r"}))
        morning(client, text="ship the resume batch")

        prompt = fake_llm.daily_prompts[0]
        assert "40 quality applications" in prompt
        assert "0 of 40" in prompt
        assert "status" in prompt
        assert "applications floor: 5" in prompt
        assert "ship the resume batch" in prompt

    def test_code_fenced_json_is_parsed(self, client: TestClient, fake_llm: FakeLlm) -> None:
        fake_llm.queue_daily('```json\n{"tasks": [{"title": "Only task"}], "rationale": "ok"}\n```')
        payload = morning(client)
        assert [task["title"] for task in payload["tasks"]] == ["Only task"]

    def test_malformed_json_falls_back_to_raw_text_task(
        self, client: TestClient, fake_llm: FakeLlm
    ) -> None:
        fake_llm.queue_daily("Sure! Here is your plan for the day: apply and gym.")
        payload = morning(client, text="apply to jobs and hit the gym")

        assert len(payload["tasks"]) == 1
        assert payload["tasks"][0]["title"] == "apply to jobs and hit the gym"
        assert "could not be parsed" in payload["plan"]["rationale"]

    def test_unknown_goal_id_is_dropped(self, client: TestClient, fake_llm: FakeLlm) -> None:
        fake_llm.queue_daily(
            json.dumps({"tasks": [{"title": "Task", "monthly_goal_id": 999}], "rationale": "r"})
        )
        payload = morning(client)
        assert payload["tasks"][0]["monthly_goal_id"] is None

    def test_resubmit_replaces_todays_plan(self, client: TestClient, fake_llm: FakeLlm) -> None:
        fake_llm.queue_daily(json.dumps({"tasks": [{"title": "Old task"}], "rationale": "r1"}))
        morning(client, text="old plan")
        fake_llm.queue_daily(
            json.dumps({"tasks": [{"title": "New A"}, {"title": "New B"}], "rationale": "r2"})
        )
        payload = morning(client, text="new plan")

        assert [task["title"] for task in payload["tasks"]] == ["New A", "New B"]
        today = client.get("/today").json()
        assert [task["title"] for task in today["tasks"]] == ["New A", "New B"]
        assert today["plan"]["raw_input"] == "new plan"

    def test_voice_input_mode_is_stored(self, client: TestClient, fake_llm: FakeLlm) -> None:
        fake_llm.queue_daily(json.dumps({"tasks": [{"title": "t"}], "rationale": "r"}))
        response = client.post(
            "/checkin/morning", json={"raw_text": "spoken words", "input_mode": "voice"}
        )
        assert response.json()["plan"]["input_mode"] == "voice"
        assert response.json()["plan"]["date"] == user_today().isoformat()

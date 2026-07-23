from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.timeutil import user_today
from app.models import Goal, ProgressLog, ProgressSource
from app.services.progress import month_bounds


def create_big(client: TestClient, title: str = "Land a junior dev role") -> dict:
    response = client.post("/goals", json={"level": "big", "title": title})
    assert response.status_code == 201
    return dict(response.json())


def create_monthly(client: TestClient, parent_id: int, **overrides: object) -> dict:
    payload: dict[str, object] = {
        "level": "monthly",
        "title": "40 quality applications",
        "parent_id": parent_id,
    }
    payload.update(overrides)
    response = client.post("/goals", json=payload)
    assert response.status_code == 201
    return dict(response.json())


def test_create_big_goal(client: TestClient) -> None:
    goal = create_big(client)
    assert goal["level"] == "big"
    assert goal["status"] == "active"
    assert goal["children"] == []
    assert goal["children_rollup"] == {"done": 0, "on_track": 0, "behind": 0}
    assert goal["percent"] is None
    assert goal["pace"] is None


def test_monthly_goal_requires_a_parent(client: TestClient) -> None:
    response = client.post("/goals", json={"level": "monthly", "title": "orphan"})
    assert response.status_code == 422


def test_monthly_parent_must_be_a_big_goal(client: TestClient) -> None:
    big = create_big(client)
    monthly = create_monthly(client, big["id"])
    response = client.post(
        "/goals",
        json={"level": "monthly", "title": "grandchild", "parent_id": monthly["id"]},
    )
    assert response.status_code == 422


def test_big_goal_cannot_have_a_parent(client: TestClient) -> None:
    big = create_big(client)
    response = client.post(
        "/goals", json={"level": "big", "title": "child big", "parent_id": big["id"]}
    )
    assert response.status_code == 422


def test_metric_goal_defaults_period_to_the_calendar_month(client: TestClient) -> None:
    big = create_big(client)
    monthly = create_monthly(
        client, big["id"], target_value=40, unit="applications", auto_source="applications"
    )
    start, end = month_bounds(user_today())
    assert monthly["period_start"] == start.isoformat()
    assert monthly["period_end"] == end.isoformat()
    assert monthly["percent"] == 0.0
    assert monthly["pace"] is not None


def test_explicit_period_is_kept(client: TestClient) -> None:
    big = create_big(client)
    monthly = create_monthly(
        client,
        big["id"],
        target_value=10,
        period_start="2026-08-01",
        period_end="2026-08-31",
    )
    assert monthly["period_start"] == "2026-08-01"
    assert monthly["period_end"] == "2026-08-31"


def test_period_must_be_set_together_and_ordered(client: TestClient) -> None:
    big = create_big(client)
    response = client.post(
        "/goals",
        json={
            "level": "monthly",
            "title": "bad period",
            "parent_id": big["id"],
            "period_start": "2026-07-01",
        },
    )
    assert response.status_code == 422
    response = client.post(
        "/goals",
        json={
            "level": "monthly",
            "title": "inverted period",
            "parent_id": big["id"],
            "period_start": "2026-07-31",
            "period_end": "2026-07-01",
        },
    )
    assert response.status_code == 422


def test_tree_nests_children_under_the_right_parent(client: TestClient) -> None:
    first_big = create_big(client, "Job search")
    second_big = create_big(client, "Health")
    create_monthly(client, first_big["id"], title="Applications")
    create_monthly(client, second_big["id"], title="Run 60 km")

    tree = client.get("/goals").json()
    assert [goal["title"] for goal in tree] == ["Job search", "Health"]
    by_title = {goal["title"]: goal for goal in tree}
    assert [c["title"] for c in by_title["Job search"]["children"]] == ["Applications"]
    assert [c["title"] for c in by_title["Health"]["children"]] == ["Run 60 km"]


def test_big_goal_rollup_counts_done_on_track_and_behind(
    client: TestClient, db_session: Session
) -> None:
    big = create_big(client)
    done_child = create_monthly(client, big["id"], title="done child")
    client.patch(f"/goals/{done_child['id']}", json={"status": "done"})
    create_monthly(client, big["id"], title="plain child stays on track")
    create_monthly(
        client,
        big["id"],
        title="behind child",
        target_value=30,
        period_start="2026-01-01",
        period_end="2026-01-31",
    )
    dropped = create_monthly(client, big["id"], title="dropped child")
    client.patch(f"/goals/{dropped['id']}", json={"status": "dropped"})

    tree = client.get("/goals").json()
    assert tree[0]["children_rollup"] == {"done": 1, "on_track": 1, "behind": 1}


def test_patch_updates_title_and_status(client: TestClient) -> None:
    big = create_big(client)
    response = client.patch(f"/goals/{big['id']}", json={"title": "New title"})
    assert response.status_code == 200
    assert response.json()["title"] == "New title"
    response = client.patch(f"/goals/{big['id']}", json={"status": "dropped"})
    assert response.json()["status"] == "dropped"


def test_patch_missing_goal_is_404(client: TestClient) -> None:
    assert client.patch("/goals/999", json={"title": "x"}).status_code == 404


def test_delete_cascades_to_children_and_their_progress(
    client: TestClient, db_session: Session
) -> None:
    big = create_big(client)
    monthly = create_monthly(client, big["id"], target_value=10)
    db_session.add(
        ProgressLog(
            goal_id=monthly["id"],
            date=date(2026, 7, 10),
            delta=3,
            source=ProgressSource.MANUAL,
        )
    )
    db_session.commit()

    assert client.delete(f"/goals/{big['id']}").status_code == 204
    assert client.get("/goals").json() == []
    assert db_session.query(Goal).count() == 0
    assert db_session.query(ProgressLog).count() == 0


def test_delete_missing_goal_is_404(client: TestClient) -> None:
    assert client.delete("/goals/999").status_code == 404


def test_non_metric_goal_never_gets_a_percent(client: TestClient, db_session: Session) -> None:
    big = create_big(client)
    monthly = create_monthly(client, big["id"], title="vague goal")
    db_session.add(
        ProgressLog(
            goal_id=monthly["id"],
            date=date(2026, 7, 10),
            delta=2,
            source=ProgressSource.MANUAL,
        )
    )
    db_session.commit()

    tree = client.get("/goals").json()
    child = tree[0]["children"][0]
    assert child["percent"] is None
    assert child["pace"] is None
    assert child["current"] == 2.0
    assert child["last_activity"] == "2026-07-10"

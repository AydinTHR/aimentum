from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AutoSource,
    DailyPlan,
    Goal,
    GoalLevel,
    GoalStatus,
    InputMode,
    ProgressLog,
    ProgressSource,
    Task,
)
from app.services.progress import goal_current, record_applications

TODAY = date(2026, 7, 23)
JULY = (date(2026, 7, 1), date(2026, 7, 31))


def make_goal_tree(
    session: Session,
    auto_source: AutoSource = AutoSource.APPLICATIONS,
    status: GoalStatus = GoalStatus.ACTIVE,
    period: tuple[date, date] | None = JULY,
    target: int | None = 40,
) -> Goal:
    big = Goal(level=GoalLevel.BIG, title="Job search")
    session.add(big)
    session.flush()
    monthly = Goal(
        level=GoalLevel.MONTHLY,
        parent_id=big.id,
        title="Applications",
        status=status,
        auto_source=auto_source,
        target_value=None if target is None else Decimal(target),
        unit="applications",
        period_start=None if period is None else period[0],
        period_end=None if period is None else period[1],
    )
    session.add(monthly)
    session.commit()
    return monthly


class TestEveningCheckinAutoLogging:
    def test_count_is_logged_to_matching_goals(self, db_session: Session) -> None:
        goal = make_goal_tree(db_session)
        record_applications(db_session, TODAY, 5)
        db_session.commit()
        assert goal_current(db_session, goal.id) == Decimal(5)

    def test_editing_a_checkin_resets_instead_of_adding(self, db_session: Session) -> None:
        goal = make_goal_tree(db_session)
        record_applications(db_session, TODAY, 5)
        record_applications(db_session, TODAY, 7)
        db_session.commit()
        assert goal_current(db_session, goal.id) == Decimal(7)
        entries = db_session.scalars(
            select(ProgressLog).where(ProgressLog.goal_id == goal.id)
        ).all()
        assert len(entries) == 1
        assert entries[0].source == ProgressSource.EVENING_CHECKIN

    def test_days_accumulate_separately(self, db_session: Session) -> None:
        goal = make_goal_tree(db_session)
        record_applications(db_session, date(2026, 7, 22), 4)
        record_applications(db_session, date(2026, 7, 23), 6)
        db_session.commit()
        assert goal_current(db_session, goal.id) == Decimal(10)

    def test_goal_outside_its_period_is_not_logged(self, db_session: Session) -> None:
        goal = make_goal_tree(db_session, period=(date(2026, 6, 1), date(2026, 6, 30)))
        record_applications(db_session, TODAY, 5)
        db_session.commit()
        assert goal_current(db_session, goal.id) == Decimal(0)

    def test_inactive_goal_is_not_logged(self, db_session: Session) -> None:
        goal = make_goal_tree(db_session, status=GoalStatus.DROPPED)
        record_applications(db_session, TODAY, 5)
        db_session.commit()
        assert goal_current(db_session, goal.id) == Decimal(0)

    def test_goal_without_the_applications_source_is_not_logged(self, db_session: Session) -> None:
        goal = make_goal_tree(db_session, auto_source=AutoSource.NONE)
        record_applications(db_session, TODAY, 5)
        db_session.commit()
        assert goal_current(db_session, goal.id) == Decimal(0)

    def test_every_matching_goal_is_logged(self, db_session: Session) -> None:
        first = make_goal_tree(db_session)
        second = make_goal_tree(db_session)
        record_applications(db_session, TODAY, 3)
        db_session.commit()
        assert goal_current(db_session, first.id) == Decimal(3)
        assert goal_current(db_session, second.id) == Decimal(3)


def make_task(session: Session, goal_id: int | None, day: date = TODAY) -> Task:
    plan = session.scalars(select(DailyPlan).where(DailyPlan.date == day)).first()
    if plan is None:
        plan = DailyPlan(date=day, raw_input="tasks", input_mode=InputMode.TEXT)
        session.add(plan)
        session.flush()
    task = Task(plan_id=plan.id, title="Apply to five roles", monthly_goal_id=goal_id, sort=0)
    session.add(task)
    session.commit()
    return task


class TestTaskCompletionAutoLogging:
    def test_completing_a_linked_task_logs_one_unit(
        self, client: TestClient, db_session: Session
    ) -> None:
        goal = make_goal_tree(db_session, auto_source=AutoSource.TASKS_DONE, target=20)
        task = make_task(db_session, goal.id)
        response = client.patch(f"/tasks/{task.id}", json={"done": True})
        assert response.status_code == 200
        assert goal_current(db_session, goal.id) == Decimal(1)

    def test_repeating_the_same_state_does_not_double_log(
        self, client: TestClient, db_session: Session
    ) -> None:
        goal = make_goal_tree(db_session, auto_source=AutoSource.TASKS_DONE, target=20)
        task = make_task(db_session, goal.id)
        client.patch(f"/tasks/{task.id}", json={"done": True})
        client.patch(f"/tasks/{task.id}", json={"done": True})
        assert goal_current(db_session, goal.id) == Decimal(1)

    def test_unchecking_removes_the_logged_unit(
        self, client: TestClient, db_session: Session
    ) -> None:
        goal = make_goal_tree(db_session, auto_source=AutoSource.TASKS_DONE, target=20)
        task = make_task(db_session, goal.id)
        client.patch(f"/tasks/{task.id}", json={"done": True})
        client.patch(f"/tasks/{task.id}", json={"done": False})
        assert goal_current(db_session, goal.id) == Decimal(0)

    def test_task_without_a_goal_logs_nothing(
        self, client: TestClient, db_session: Session
    ) -> None:
        task = make_task(db_session, None)
        response = client.patch(f"/tasks/{task.id}", json={"done": True})
        assert response.status_code == 200
        assert db_session.query(ProgressLog).count() == 0

    def test_task_linked_to_a_non_tasks_done_goal_logs_nothing(
        self, client: TestClient, db_session: Session
    ) -> None:
        goal = make_goal_tree(db_session, auto_source=AutoSource.APPLICATIONS)
        task = make_task(db_session, goal.id)
        client.patch(f"/tasks/{task.id}", json={"done": True})
        assert goal_current(db_session, goal.id) == Decimal(0)

    def test_missing_task_is_404(self, client: TestClient) -> None:
        assert client.patch("/tasks/999", json={"done": True}).status_code == 404


class TestManualQuickAdd:
    def test_manual_progress_accumulates(self, client: TestClient, db_session: Session) -> None:
        goal = make_goal_tree(db_session, auto_source=AutoSource.NONE, target=10)
        first = client.post(f"/goals/{goal.id}/progress", json={"delta": 3, "note": "warm intro"})
        assert first.status_code == 201
        assert first.json()["current"] == 3.0
        second = client.post(f"/goals/{goal.id}/progress", json={"delta": 2})
        assert second.json()["current"] == 5.0
        entry = first.json()["entry"]
        assert entry["source"] == "manual"
        assert entry["note"] == "warm intro"

    def test_manual_progress_on_missing_goal_is_404(self, client: TestClient) -> None:
        assert client.post("/goals/999/progress", json={"delta": 1}).status_code == 404

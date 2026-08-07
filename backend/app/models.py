import enum
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class GoalLevel(enum.StrEnum):
    BIG = "big"
    MONTHLY = "monthly"


class GoalStatus(enum.StrEnum):
    ACTIVE = "active"
    DONE = "done"
    DROPPED = "dropped"


class AutoSource(enum.StrEnum):
    NONE = "none"
    APPLICATIONS = "applications"
    TASKS_DONE = "tasks_done"


class InputMode(enum.StrEnum):
    TEXT = "text"
    VOICE = "voice"


class ProgressSource(enum.StrEnum):
    EVENING_CHECKIN = "evening_checkin"
    TASK = "task"
    MANUAL = "manual"


def str_enum(enum_cls: type[enum.StrEnum], name: str) -> SAEnum:
    """A plain varchar-backed enum: no native Postgres enum types to migrate."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        length=30,
        values_callable=lambda cls: [member.value for member in cls],
    )


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[GoalLevel] = mapped_column(str_enum(GoalLevel, "goal_level"))
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    target_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[GoalStatus] = mapped_column(
        str_enum(GoalStatus, "goal_status"), default=GoalStatus.ACTIVE, server_default="active"
    )
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    unit: Mapped[str | None] = mapped_column(String(50))
    auto_source: Mapped[AutoSource] = mapped_column(
        str_enum(AutoSource, "auto_source"), default=AutoSource.NONE, server_default="none"
    )
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    parent: Mapped["Goal | None"] = relationship(back_populates="children", remote_side=[id])
    children: Mapped[list["Goal"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan", order_by="Goal.id"
    )
    progress_entries: Mapped[list["ProgressLog"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan"
    )


class DailyPlan(Base):
    __tablename__ = "daily_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True)
    raw_input: Mapped[str] = mapped_column(Text)
    input_mode: Mapped[InputMode] = mapped_column(str_enum(InputMode, "input_mode"))
    rationale: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="Task.sort"
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("daily_plans.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    monthly_goal_id: Mapped[int | None] = mapped_column(
        ForeignKey("goals.id", ondelete="SET NULL"), index=True
    )
    done: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    sort: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    gcal_event_id: Mapped[str | None] = mapped_column(String(200))
    block_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    block_minutes: Mapped[int | None] = mapped_column(Integer)

    plan: Mapped[DailyPlan] = relationship(back_populates="tasks")
    monthly_goal: Mapped[Goal | None] = relationship()


class Checkin(Base):
    __tablename__ = "checkins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True)
    applications_sent: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)
    reflection: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProgressLog(Base):
    __tablename__ = "progress_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    delta: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    source: Mapped[ProgressSource] = mapped_column(str_enum(ProgressSource, "progress_source"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    goal: Mapped[Goal] = relationship(back_populates="progress_entries")


class Retro(Base):
    __tablename__ = "retros"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    week_start: Mapped[date] = mapped_column(Date, unique=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(Text)
    auth: Mapped[str] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobRun(Base):
    __tablename__ = "job_runs"
    __table_args__ = (UniqueConstraint("job", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job: Mapped[str] = mapped_column(String(50))
    date: Mapped[date] = mapped_column(Date)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PushLog(Base):
    """Audit trail for every push send attempt.

    subscription_id is nullable and survives pruning: when a dead
    subscription is deleted the FK is set to null rather than cascading the
    log rows away. Web push has no delivery receipts, so this history is the
    only evidence a send was attempted, and losing it the moment an endpoint
    expires would defeat the point. `endpoint` keeps the target readable
    after the subscription row is gone.
    """

    __tablename__ = "push_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job: Mapped[str] = mapped_column(String(50))
    subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("push_subscriptions.id", ondelete="SET NULL"), index=True
    )
    endpoint: Mapped[str] = mapped_column(Text, server_default="")
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(200))


class AppSettings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    applications_floor: Mapped[int] = mapped_column(Integer, default=5, server_default=text("5"))
    read_back_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    time_blocking_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    workday_start: Mapped[time] = mapped_column(
        Time, default=time(9, 0), server_default=text("'09:00:00'")
    )
    workday_end: Mapped[time] = mapped_column(
        Time, default=time(18, 0), server_default=text("'18:00:00'")
    )

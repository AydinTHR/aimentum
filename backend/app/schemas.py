from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import AutoSource, GoalLevel, GoalStatus, InputMode
from app.services.progress import PaceStatus


class PaceOut(BaseModel):
    expected: float
    status: PaceStatus


class ChildrenRollup(BaseModel):
    done: int
    on_track: int
    behind: int


class GoalCreate(BaseModel):
    level: GoalLevel
    title: str = Field(min_length=1, max_length=200)
    parent_id: int | None = None
    target_date: date | None = None
    target_value: Decimal | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, max_length=50)
    auto_source: AutoSource = AutoSource.NONE
    period_start: date | None = None
    period_end: date | None = None


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: GoalStatus | None = None
    target_date: date | None = None
    target_value: Decimal | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, max_length=50)
    auto_source: AutoSource | None = None
    period_start: date | None = None
    period_end: date | None = None


class GoalOut(BaseModel):
    id: int
    level: GoalLevel
    parent_id: int | None
    title: str
    target_date: date | None
    status: GoalStatus
    target_value: float | None
    unit: str | None
    auto_source: AutoSource
    period_start: date | None
    period_end: date | None
    current: float
    percent: float | None
    pace: PaceOut | None
    last_activity: date | None
    tasks_done_7d: int
    children: list["GoalOut"] = []
    children_rollup: ChildrenRollup | None = None


class ProgressAdd(BaseModel):
    delta: Decimal
    note: str | None = None


class ProgressEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    goal_id: int
    date: date
    delta: float
    source: str
    note: str | None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    title: str
    monthly_goal_id: int | None
    done: bool
    sort: int
    block_start: datetime | None
    block_minutes: int | None


class TaskPatch(BaseModel):
    done: bool


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    raw_input: str
    input_mode: InputMode
    rationale: str | None


class CheckinOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    applications_sent: int
    note: str | None
    reflection: str


class TodayOut(BaseModel):
    date: date
    plan: PlanOut | None
    tasks: list[TaskOut]
    checkin: CheckinOut | None


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    applications_floor: int
    read_back_enabled: bool
    time_blocking_enabled: bool
    workday_start: time
    workday_end: time


class SettingsPatch(BaseModel):
    applications_floor: int | None = Field(default=None, ge=0)
    read_back_enabled: bool | None = None
    time_blocking_enabled: bool | None = None
    workday_start: time | None = None
    workday_end: time | None = None


class MorningCheckinIn(BaseModel):
    raw_text: str = Field(min_length=1, max_length=5000)
    input_mode: InputMode = InputMode.TEXT


class MorningPlanOut(BaseModel):
    plan: PlanOut
    tasks: list[TaskOut]


class TranscriptOut(BaseModel):
    transcript: str


class TaskStateIn(BaseModel):
    id: int
    done: bool


class EveningCheckinIn(BaseModel):
    applications_sent: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=2000)
    task_states: list[TaskStateIn] = []


class EveningCheckinOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    checkin: CheckinOut
    summary: dict[str, object]


class RetroOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    week_start: date
    body: str

// Hand-mirrored from backend/app/schemas.py. One user, one API, one place
// to update when a shape changes; codegen would be heavier than the schemas.

export type PaceStatus = "ahead" | "on_track" | "behind";
export type GoalLevel = "big" | "monthly";
export type GoalStatus = "active" | "done" | "dropped";
export type AutoSource = "none" | "applications" | "tasks_done";
export type InputMode = "text" | "voice";

export interface Pace {
  expected: number;
  status: PaceStatus;
}

export interface ChildrenRollup {
  done: number;
  on_track: number;
  behind: number;
}

export interface Goal {
  id: number;
  level: GoalLevel;
  parent_id: number | null;
  title: string;
  target_date: string | null;
  status: GoalStatus;
  target_value: number | null;
  unit: string | null;
  auto_source: AutoSource;
  period_start: string | null;
  period_end: string | null;
  current: number;
  percent: number | null;
  pace: Pace | null;
  last_activity: string | null;
  tasks_done_7d: number;
  children: Goal[];
  children_rollup: ChildrenRollup | null;
}

export interface Task {
  id: number;
  plan_id: number;
  title: string;
  monthly_goal_id: number | null;
  done: boolean;
  sort: number;
  block_start: string | null;
  block_minutes: number | null;
  gcal_event_id: string | null;
}

export interface Plan {
  id: number;
  date: string;
  raw_input: string;
  input_mode: InputMode;
  rationale: string | null;
}

export interface Checkin {
  id: number;
  date: string;
  applications_sent: number;
  note: string | null;
  reflection: string;
}

export interface Today {
  date: string;
  plan: Plan | null;
  tasks: Task[];
  checkin: Checkin | null;
}

export interface MorningPlan {
  plan: Plan;
  tasks: Task[];
}

export interface EveningResult {
  checkin: Checkin;
  summary: ProgressSummary;
}

export interface SummaryGoal {
  id: number;
  title: string;
  unit: string | null;
  current: number;
  target: number | null;
  percent: number | null;
  pace: Pace | null;
}

export interface ProgressSummary {
  date: string;
  applications_floor: number;
  applications_sent_today: number | null;
  goals: SummaryGoal[];
}

export interface CalendarEvent {
  summary: string;
  start: string;
  end: string;
  all_day: boolean;
  calendar: string;
}

export interface CalendarDay {
  date: string;
  available: boolean;
  events: CalendarEvent[];
}

export interface Settings {
  applications_floor: number;
  read_back_enabled: boolean;
  time_blocking_enabled: boolean;
  workday_start: string;
  workday_end: string;
}

export interface SettingsPatch {
  applications_floor?: number;
  read_back_enabled?: boolean;
  time_blocking_enabled?: boolean;
  workday_start?: string;
  workday_end?: string;
}

export interface Retro {
  id: number;
  week_start: string;
  body: string;
}

export interface PushTestResult {
  sent: number;
  statuses: string[];
  pruned: number;
}

export interface GoalCreate {
  level: GoalLevel;
  title: string;
  parent_id?: number | null;
  target_date?: string | null;
  target_value?: number | null;
  unit?: string | null;
  auto_source?: AutoSource;
  period_start?: string | null;
  period_end?: string | null;
}

import type {
  CalendarDay,
  EveningResult,
  Goal,
  GoalCreate,
  InputMode,
  MorningPlan,
  ProgressSummary,
  PushTestResult,
  Retro,
  Settings,
  SettingsPatch,
  Task,
  Today,
} from "./types";

export const API_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

const TOKEN_KEY = "aimentum.token";

type Listener = () => void;
const listeners = new Set<Listener>();

/** The shared bearer token, kept in localStorage and observable so the
 * token gate re-renders the moment a 401 clears it. */
export const tokenStore = {
  get(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  },
  set(token: string): void {
    localStorage.setItem(TOKEN_KEY, token);
    listeners.forEach((listener) => listener());
  },
  clear(): void {
    localStorage.removeItem(TOKEN_KEY);
    listeners.forEach((listener) => listener());
  },
  subscribe(listener: Listener): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

export class ApiError extends Error {
  status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body !== undefined && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Could not reach the server. Check your connection.");
  }

  if (response.status === 401) {
    // The shared token was rejected: drop it so the gate takes over.
    tokenStore.clear();
    throw new ApiError(401, "Your access token was not accepted.");
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body: unknown = await response.json();
      if (
        typeof body === "object" &&
        body !== null &&
        "detail" in body &&
        typeof (body as { detail: unknown }).detail === "string"
      ) {
        detail = (body as { detail: string }).detail;
      }
    } catch {
      // A non-JSON error body keeps the generic message.
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Check a token without storing it.
 *
 * The gate cannot just save the token and let the first request fail: saving
 * it renders the app, and the 401 that arrives a moment later would unmount
 * the gate before it could explain itself. So the token is proven first and
 * stored second.
 */
export async function verifyToken(candidate: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/settings`, {
      headers: { Authorization: `Bearer ${candidate}` },
    });
  } catch {
    throw new ApiError(0, "Could not reach the server. Check your connection.");
  }
  if (response.status === 401) {
    throw new ApiError(401, "That token was not accepted.");
  }
  if (!response.ok) {
    throw new ApiError(response.status, `The server answered with ${response.status}.`);
  }
}

export const api = {
  today: () => request<Today>("/today"),
  progressSummary: () => request<ProgressSummary>("/progress/summary"),
  calendarToday: () => request<CalendarDay>("/calendar/today"),

  morningCheckin: (rawText: string, inputMode: InputMode) =>
    request<MorningPlan>("/checkin/morning", {
      method: "POST",
      body: JSON.stringify({ raw_text: rawText, input_mode: inputMode }),
    }),
  transcribe: (audio: Blob, filename: string) => {
    const form = new FormData();
    form.append("file", audio, filename);
    return request<{ transcript: string }>("/checkin/morning/audio", {
      method: "POST",
      body: form,
    });
  },
  eveningCheckin: (
    applicationsSent: number,
    note: string | null,
    taskStates: { id: number; done: boolean }[],
  ) =>
    request<EveningResult>("/checkin/evening", {
      method: "POST",
      body: JSON.stringify({
        applications_sent: applicationsSent,
        note,
        task_states: taskStates,
      }),
    }),
  setTaskDone: (taskId: number, done: boolean) =>
    request<Task>(`/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify({ done }) }),

  goals: () => request<Goal[]>("/goals"),
  createGoal: (goal: GoalCreate) =>
    request<Goal>("/goals", { method: "POST", body: JSON.stringify(goal) }),
  addProgress: (goalId: number, delta: number, note?: string) =>
    request<unknown>(`/goals/${goalId}/progress`, {
      method: "POST",
      body: JSON.stringify({ delta, note: note ?? null }),
    }),

  retros: () => request<Retro[]>("/retros"),

  settings: () => request<Settings>("/settings"),
  patchSettings: (patch: SettingsPatch) =>
    request<Settings>("/settings", { method: "PATCH", body: JSON.stringify(patch) }),

  vapidPublicKey: () => request<{ public_key: string }>("/push/public-key"),
  pushSubscribe: (subscription: {
    endpoint: string;
    keys: { p256dh: string; auth: string };
    user_agent?: string;
  }) =>
    request<{ id: number; endpoint: string }>("/push/subscribe", {
      method: "POST",
      body: JSON.stringify(subscription),
    }),
  pushUnsubscribe: (endpoint: string) =>
    request<void>("/push/subscribe", { method: "DELETE", body: JSON.stringify({ endpoint }) }),
  pushTest: () => request<PushTestResult>("/push/test", { method: "POST" }),
};

export type Api = typeof api;

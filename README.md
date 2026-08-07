# Aimentum

[![CI](https://github.com/AydinTHR/aimentum/actions/workflows/ci.yml/badge.svg)](https://github.com/AydinTHR/aimentum/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://www.conventionalcommits.org)

A single-user AI accountability agent that plans your day, tracks goal pace honestly, and reaches out at the right moment.

## Why this exists

Job searches and personal goals fail quietly: not from a lack of plans, but from nobody
checking in on them. Aimentum is an accountability agent, not a todo app. It initiates
the contact: a morning push to plan the day by voice, a nudge if the plan never arrived,
an evening check-in that records what actually happened, and a Sunday retro written by
Claude from the week's real numbers. Metric goals carry an honest pace status (ahead, on
track, behind) computed against how much of their period has elapsed, and that pace
drives what the agent says and pushes.

## Status

Phase 5: Google Calendar. What exists today:

- The agent reads the day's real events across your calendars and prioritizes
  around them, and serves them to the Today screen at `GET /calendar/today`
- Time blocks for the day's tasks are written into one dedicated Aimentum
  calendar, so Google's own apps stay the calendar experience
- Overlap checks and workday clamping happen in code, never in the prompt:
  Claude proposes a time, the backend decides whether it survives
- Re-planning deletes the blocks the previous plan created, via stored event
  ids, so the calendar never accumulates stale entries
- Losing Calendar degrades rather than breaks: planning still happens without
  meetings, and the rationale says the calendar was unreachable

From Phase 4, push and scheduling (the product's priority zero):

- Web push over VAPID with subscribe, unsubscribe, and a send-test endpoint
  the Settings screen calls to verify a device
- Every send attempt written to `push_log` with its outcome, and dead
  subscriptions pruned automatically when a gateway reports 404 or 410
- `POST /tick` for the four scheduled jobs, authenticated by its own secret
  header, claiming each job in `job_runs` before returning 202 and doing the
  work in a background task
- The nudge job checks for an existing plan before sending, and the evening
  push carries the live pace line in the notification itself

From Phase 3, the agent brain:

- Morning planning: free text (or a voice transcript) goes in, Claude parses
  it into ordered tasks with goal links and a one-line priority rationale,
  weighing each metric goal's live pace numbers and the applications floor
- Voice check-ins: audio uploads are transcoded to FLAC with ffmpeg and
  transcribed server-side via Google Speech-to-Text behind a swappable
  Protocol; the transcript comes back for a human confirm before it becomes
  the plan
- Evening check-in: task states and the applications count are recorded (auto
  feeding the goal ledger), and Claude writes a short reflection citing the
  real numbers, hard-capped at 400 characters in code
- Weekly retro generation with a 1200 character cap, plus retro endpoints
- Prompts live as versioned files in backend/app/prompts, never inline
- The agent test suite runs with a mocked Anthropic client and a fake
  transcriber: zero real API calls

From Phase 2:

- Postgres data model (goals, plans, tasks, check-ins, progress ledger, retros,
  push subscriptions, job runs, settings) with Alembic migrations
- Bearer token auth on every endpoint except `/health`
- Goals CRUD returning a nested tree with computed current, percent, and pace
- A single progress service owning all progress and pace math: metric goals get
  honest progress bars, vague goals never get a fake percent, and pace status
  (ahead, on track, behind) is computed against how much of the period has elapsed
- Auto-logged progress: evening application counts and completed linked tasks
  move the bars without bookkeeping
- `/today`, `/progress/summary`, and settings endpoints for the PWA to come
- React + Vite + Tailwind frontend rendering a placeholder shell
- CI runs the backend suite against a real Postgres service

Coming next, in order: the installable PWA, and deployment.

## Notification reliability

Notifications are the whole product: a push that arrives late or dies quietly
is the app not existing that day. Web push has no delivery receipts, so there
is no acknowledgement to check. Reliability is proven two ways instead, and
the honest limitation is that neither is a receipt from the device:

- Every send attempt is written to `push_log` with the gateway's status, and
  the log row outlives its subscription so pruning never erases the evidence
- A 48-hour soak against a real phone before deployment is called done, with
  every scheduled push checked off against `push_log`

Scheduling lives outside the process for the same reason. The backend sleeps
on Render's free tier, so an in-process scheduler would sleep through its own
alarms; cron-job.org calls `/tick` instead, with warmup requests a few minutes
ahead to absorb cold starts.

## Connecting Google Calendar

The only OAuth in this project is the backend's own one-time connection to
the owner's Google account. There is no user-facing sign-in.

Before running anything: create an OAuth client of type **Desktop** in your
Google Cloud project, enable the Calendar API, and set the consent screen to
**In production**. Leaving it in Testing mode expires refresh tokens after
seven days, so calendar access would die every week without any visible
cause. Put the client id and secret in `backend/.env`, then:

```bash
cd backend
uv run python scripts/google_oauth.py           # browser flow, prints the refresh token
uv run python scripts/google_calendar_setup.py  # creates the calendar, prints its id
```

Paste both values into `backend/.env`. The setup script finds or creates a
calendar named Aimentum; the agent writes only there and never touches your
own calendars except to read them.

### Real-account smoke test

With the values in place, run the backend and check the round trip:

```bash
curl -s "$API/calendar/today" -H "$AUTH"        # should list today's real events
```

Then submit a morning check-in with time blocking on and confirm in Google
Calendar that the blocks appear in the Aimentum calendar, sit inside your
workday window, and avoid your existing meetings. Submit a second check-in
for the same day and confirm the first set of blocks disappears rather than
piling up. To check the degradation path, unset `GOOGLE_OAUTH_REFRESH_TOKEN`
and submit again: the plan should still be created, with no blocks and a
rationale that says the calendar was unreachable.

### Generating VAPID keys

One command, run once. Paste the output into `backend/.env`, and give the
frontend the same public key as `VITE_VAPID_PUBLIC_KEY`.

```bash
cd backend && uv run python -c "
from py_vapid import Vapid01
from py_vapid.utils import b64urlencode
from cryptography.hazmat.primitives import serialization
v = Vapid01(); v.generate_keys()
print('VAPID_PUBLIC_KEY=' + b64urlencode(v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)))
print('VAPID_PRIVATE_KEY=' + b64urlencode(v.private_key.private_numbers().private_value.to_bytes(32, 'big')))
"
```

## Architecture

The frontend is an installable PWA (Vercel) talking to a client-agnostic FastAPI JSON
API (Render, Docker) backed by Postgres (Neon). Scheduling is external: cron-job.org
hits a secured `/tick` endpoint, because the free-tier backend spins down when idle and
an in-process scheduler would sleep through its own alarms. Claude (Anthropic API)
writes the plans, reflections, and retros; Google Cloud Speech-to-Text transcribes
voice check-ins server-side; Google Calendar provides the calendar, which the agent
reads and writes rather than reimplementing. The decisions and their trade-offs live in
[docs/adr](./docs/adr).

## Repository layout

```
backend/    FastAPI API: app/ (routers, core config), tests/
frontend/   React + Vite + Tailwind PWA
docs/adr/   architecture decision records
```

## Local development

The database is hosted, so running the app needs no Docker and no local
Postgres. Point `DATABASE_URL` at a [Neon](https://neon.com) project (free
tier) and the backend talks straight to it.

Backend (Python 3.12):

```bash
cd backend
uv sync --extra dev
cp .env.example .env                         # set APP_TOKEN and DATABASE_URL
uv run alembic upgrade head                  # create the schema
uv run uvicorn app.main:app --reload         # http://localhost:8000/health
```

Frontend:

```bash
cd frontend
npm install
npm run dev                                  # http://localhost:5173
npm run test
```

### Running the tests

The suite drops and rebuilds its schema on every run, so it uses its own
database and refuses to touch a non-local host. That guard is deliberate:
with a hosted development database, a stray `TEST_DATABASE_URL` would be the
difference between a test run and losing real data.

```bash
docker compose up -d db                      # Postgres 16, only needed for tests
cd backend && uv run pytest
```

To run tests without Docker at all, create a throwaway Neon branch and opt in
explicitly, understanding that its schema gets dropped on every run:

```bash
TEST_DATABASE_URL=<throwaway branch url> ALLOW_REMOTE_TEST_DB=1 uv run pytest
```

## API

Every endpoint except `/health` requires the bearer token from `backend/.env`.
A quick tour with curl:

```bash
API=http://localhost:8000
AUTH="Authorization: Bearer change-me"        # your APP_TOKEN
JSON="Content-Type: application/json"

# Create the big goal, then a metric monthly goal under it. The monthly goal
# defaults its period to the current calendar month and auto-logs progress
# from evening application counts.
curl -s -X POST "$API/goals" -H "$AUTH" -H "$JSON" \
  -d '{"level": "big", "title": "Land a junior dev role"}'
curl -s -X POST "$API/goals" -H "$AUTH" -H "$JSON" \
  -d '{"level": "monthly", "parent_id": 1, "title": "40 quality applications",
       "target_value": 40, "unit": "applications", "auto_source": "applications"}'

# Log manual progress; the response carries the updated total.
curl -s -X POST "$API/goals/1/progress" -H "$AUTH" -H "$JSON" \
  -d '{"delta": 1, "note": "networking coffee"}'

# The goal tree: big goals with monthly children, each with current, percent,
# and pace (ahead, on_track, behind).
curl -s "$API/goals" -H "$AUTH"

# The Today card payload: applications floor plus each metric goal's bar.
curl -s "$API/progress/summary" -H "$AUTH"

# Today's plan, tasks, and check-in state; empty on a fresh day.
curl -s "$API/today" -H "$AUTH"

# Settings, including the daily applications floor.
curl -s "$API/settings" -H "$AUTH"
curl -s -X PATCH "$API/settings" -H "$AUTH" -H "$JSON" -d '{"applications_floor": 6}'

# Morning check-in: Claude parses and prioritizes the day (needs ANTHROPIC_API_KEY).
curl -s -X POST "$API/checkin/morning" -H "$AUTH" -H "$JSON" \
  -d '{"raw_text": "send 5 applications, gym, call the landlord", "input_mode": "text"}'

# Voice path: upload a recording, get the transcript back for confirm-or-edit.
curl -s -X POST "$API/checkin/morning/audio" -H "$AUTH" -F "file=@clip.m4a"

# Evening check-in: check off tasks, log the applications count, get the reflection.
curl -s -X POST "$API/checkin/evening" -H "$AUTH" -H "$JSON" \
  -d '{"applications_sent": 6, "note": "good day", "task_states": [{"id": 1, "done": true}]}'

# Weekly retros.
curl -s "$API/retros/latest" -H "$AUTH"

# Today's agenda. Reports availability rather than failing when Calendar is down.
curl -s "$API/calendar/today" -H "$AUTH"

# Register a device for push, then verify it with a test notification.
curl -s -X POST "$API/push/subscribe" -H "$AUTH" -H "$JSON" \
  -d '{"endpoint": "https://fcm.googleapis.com/fcm/send/...",
       "keys": {"p256dh": "...", "auth": "..."}, "user_agent": "iPhone Safari"}'
curl -s -X POST "$API/push/test" -H "$AUTH"
```

The scheduler calls `/tick` with its own secret, never the bearer token.
Calling it twice for the same job and day sends once: the second call is
turned away by the `job_runs` claim.

```bash
curl -s -X POST "$API/tick?job=morning" -H "X-Tick-Secret: $TICK_SECRET"
# {"job":"morning","date":"2026-08-07","status":"scheduled"}
curl -s -X POST "$API/tick?job=morning" -H "X-Tick-Secret: $TICK_SECRET"
# {"job":"morning","date":"2026-08-07","status":"already_ran"}
```

## Development workflow

```bash
pre-commit run --all-files   # optional: run the formatters and linters locally
```

- Branching: short-lived feature branches off `main`, merged via pull request.
- Commits: [Conventional Commits](https://www.conventionalcommits.org).
- Tests and lint run in CI on every pull request and must pass before merge.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md). By participating you agree to the
[Code of Conduct](./CODE_OF_CONDUCT.md).

## License

[MIT](./LICENSE) (c) 2026 Aydin.

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

Phase 3: the agent brain. What exists today:

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

Coming next, in order: push and scheduling, Google Calendar integration, the
installable PWA, and deployment.

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

Backend (Python 3.12):

```bash
docker compose up -d db                      # Postgres 16 on localhost:5432

cd backend
uv sync --extra dev
cp .env.example .env                         # set APP_TOKEN, keep the local DATABASE_URL
uv run alembic upgrade head                  # create the schema
uv run uvicorn app.main:app --reload         # http://localhost:8000/health
uv run pytest                                # uses its own aimentum_test database
```

Frontend:

```bash
cd frontend
npm install
npm run dev                                  # http://localhost:5173
npm run test
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

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

Phase 1 walking skeleton. What exists today:

- FastAPI backend serving `GET /health`
- React + Vite + Tailwind frontend rendering a placeholder shell
- Local Postgres 16 via Docker Compose
- CI (ruff, mypy, pytest, oxlint, prettier, vitest, build) on every pull request
- ADRs 0001 through 0005 fixing the architecture

Coming next, in order: database and core API, the agent brain (Claude planning,
reflection, retro, speech to text), push and scheduling, Google Calendar integration,
the installable PWA, and deployment.

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
uv venv --python 3.12 && uv pip install -e ".[dev]"
cp .env.example .env
uv run uvicorn app.main:app --reload         # http://localhost:8000/health
uv run pytest
```

Frontend:

```bash
cd frontend
npm install
npm run dev                                  # http://localhost:5173
npm run test
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

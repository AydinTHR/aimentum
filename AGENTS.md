# AGENTS.md

Guidance for AI coding agents, and humans, working in Aimentum.

## Overview

Aimentum is a single-user AI accountability agent. It plans the owner's day from a
voice or text check-in, prioritizes around the real calendar, tracks goal pace honestly,
and reaches out through push notifications at the right moments. It is agent-initiated
by design: the app contacts the owner, not the other way around. Never describe it as a
todo app in code, docs, or copy.

## Repository structure

- `backend/`: FastAPI JSON API (Python 3.12). `app/` holds routers, core config, and
  domain logic; `tests/` mirrors it. The API stays client-agnostic so future clients
  can be added with zero backend changes.
- `frontend/`: React + Vite + Tailwind app, an installable PWA.
- `docs/adr/`: architecture decision records. Read these before changing structure.
  ADR-0001 through ADR-0005 fix the big choices; do not relitigate them in code.

## Setup

```bash
docker compose up -d db                      # local Postgres 16

cd backend
uv venv --python 3.12 && uv pip install -e ".[dev]"
cp .env.example .env

cd ../frontend
npm install
```

## Testing and checks

Run these before proposing any change, and make them pass:

```bash
cd backend && ruff check . && ruff format --check . && mypy app && pytest
cd frontend && npm run lint && npm run format:check && npm run test && npm run build
pre-commit run --all-files                   # from the repo root
```

## Conventions

- Conventional Commits for every commit. The type drives the changelog and version bump.
- Short-lived feature branches off main, squash and merge.
- Write or update a test alongside the code, never after the fact.
- All user-facing times are America/Toronto; the database stores UTC.
- External integrations sit behind Protocols (speech to text, calendar) so providers
  are swappable in one class.
- Progress and pace math lives in one tested backend service module, never in prompts
  and never in the UI.
- Claude prompts are versioned files under `backend/app/prompts/`, never inline strings.

## Where to look first

Start with README.md, then the records in `docs/adr/`. The ADRs carry the reasoning
behind the architecture; the README carries the product behavior.

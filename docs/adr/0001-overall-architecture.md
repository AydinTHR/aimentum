# 1. Overall architecture: installable PWA, FastAPI API, external scheduling

- Status: accepted
- Date: 2026-07-18

## Context

Aimentum is a single-user accountability agent for its owner. The product thesis is
agent-initiated contact: push notifications at the right moments, voice-first morning
planning, calendar-aware prioritization, and Claude-written reviews. It is also a
portfolio project, so the engineering must look production-minded while running on free
tiers with near-zero fixed cost. Notification reliability is the top priority; a push
that fails silently is the app not existing that day.

## Decision

We will build a single repository with two applications:

- `backend/`: Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Postgres. A clean,
  client-agnostic JSON API secured by one shared bearer token from an env var. Single
  user by design: no signup, no multi-tenancy.
- `frontend/`: React + Vite + Tailwind, shipped as an installable PWA with Web Push.

Hosting is all free tiers: backend on Render (as a Docker image), frontend on Vercel,
database on Neon, scheduling on cron-job.org, speech to text within Google's free
monthly minutes, Google Calendar API at no charge. The only recurring cost is Anthropic
API usage. Scheduling lives outside the process (see ADR-0002). AI calls use the
Anthropic API with a small daily model and a larger weekly model, both configurable via
env. All user-facing times are America/Toronto; the database stores UTC.

## Consequences

- The whole system runs for pennies a day, which keeps the agent honest as a personal
  tool rather than a demo.
- Free tiers bring cold starts and spin-downs, so reliability work (warmup pings, send
  logging, idempotent jobs) is part of the architecture, not an afterthought.
- A client-agnostic API means a future native iOS client can be added with zero backend
  changes (see ADR-0003).
- Single-user auth is one bearer token: simple and sufficient, but it must never be
  committed, and rotating it means updating one env var on each side.

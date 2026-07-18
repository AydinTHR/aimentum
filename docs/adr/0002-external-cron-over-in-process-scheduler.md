# 2. External cron hitting /tick instead of an in-process scheduler

- Status: accepted
- Date: 2026-07-18

## Context

The agent's touchpoints are scheduled: a morning planning push, a mid-morning nudge, an
evening check-in push, and a Sunday retro. The obvious implementation is an in-process
scheduler such as APScheduler. But the backend runs on Render's free tier, which spins
the service down when idle. A sleeping process cannot fire its own scheduler, so the
morning push would simply never arrive on any day the app was not already awake. That
failure mode directly attacks the product's priority zero.

## Decision

We will not run any in-process scheduler. Scheduling is external: cron-job.org calls a
secured `POST /tick?job=...` endpoint on the backend at each scheduled time,
authenticated with an `X-Tick-Secret` header. The endpoint validates the secret, checks
idempotency against a `job_runs` table keyed on (job, date), returns 202 immediately,
and performs the real work (Claude calls, push sends) in FastAPI BackgroundTasks.
Warmup requests to `/health` are scheduled a few minutes before every job to absorb
Render cold starts, and cron retries on failure are enabled.

## Consequences

- Scheduled work fires even though the backend sleeps between requests, at the cost of
  depending on an external scheduler service.
- The instant 202 keeps cron-job.org from timing out on slow cold starts; the actual
  work happens after the response.
- Idempotency via `job_runs` makes cron retries safe: a job runs at most once per day.
- The `/tick` endpoint is part of the public surface and must stay secured and boring:
  no business logic in the handler beyond dispatch.

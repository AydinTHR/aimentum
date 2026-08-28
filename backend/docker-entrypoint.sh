#!/bin/sh
# Migrate, then serve.
#
# Migrations run here because Render's free plan has no pre-deploy command.
# Two rules make that safe: the server never starts on a failed migration,
# and uvicorn replaces this shell so it receives Render's SIGTERM itself.
set -eu

# alembic.ini resolves its script directory relative to itself and prepends
# "." to sys.path, so alembic only works from the application root.
cd /app

# A suspended Neon compute takes a few seconds to wake and a restart can land
# in exactly that window, so a first failure is often not a real one. Give up
# loudly after three: a container that started against an un-migrated schema
# would answer /health while every real request failed, and Render's health
# check would call that healthy.
attempt=1
until alembic upgrade head; do
    if [ "${attempt}" -ge 3 ]; then
        echo "aimentum: migrations failed after ${attempt} attempts, refusing to start" >&2
        exit 1
    fi
    echo "aimentum: migration attempt ${attempt} failed, retrying in 5s" >&2
    attempt=$((attempt + 1))
    sleep 5
done

# One line in the log naming the revision this instance is on. Never fatal:
# an informational query must not be the reason the API is down.
alembic current || echo "aimentum: could not read the current revision" >&2

# exec, not a plain call, so uvicorn replaces this shell and becomes PID 1.
#
# Docker delivers signals only to PID 1, and /bin/sh does not forward them to
# a child. Without exec, uvicorn never sees Render's SIGTERM, never starts a
# graceful shutdown, and is killed outright when the stop window closes. That
# window is where the notifications live: POST /tick claims its job in
# job_runs, commits, returns 202, and sends the push from a background task.
# Starlette awaits that task inside the response, so uvicorn still counts the
# request as in flight and a graceful shutdown waits for it. Kill the process
# instead and the job stays claimed with nothing sent, while cron's retry is
# turned away with already_ran: a notification that silently never arrives.
#
# 25 seconds sits inside Render's default 30 second shutdown delay, leaving
# uvicorn room to exit on its own terms rather than being killed mid send.
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --timeout-graceful-shutdown 25

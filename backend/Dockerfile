# The API as Render runs it.
#
# Deliberately plain Dockerfile syntax: no syntax directive, no BuildKit
# cache mounts, no COPY --chmod. This same file has to build on a laptop, in
# GitHub Actions, and on Render's builder, and a feature one of them lacks is
# a failed deploy that has nothing to do with the code.

# Pinned to the uv that produced uv.lock, and named so Dependabot's docker
# ecosystem tracks it like any other dependency.
FROM ghcr.io/astral-sh/uv:0.12.9 AS uv


FROM python:3.12-slim-bookworm AS builder

COPY --from=uv /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# The manifest and lockfile alone, so editing a router does not reinstall
# every dependency. Dependencies come from uv.lock rather than the loose
# specifiers CI resolves: CI should find out when a new release breaks us,
# the image should contain exactly what was tested. --locked turns a lockfile
# that has drifted from pyproject.toml into a red build rather than an image
# nobody ran the suite against.
#
# --no-install-project keeps the app itself out of the virtualenv. The source
# is copied into the runtime stage and reached through PYTHONPATH, which
# leaves exactly one copy of it in the image.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project


FROM python:3.12-slim-bookworm

# ffmpeg ships ffprobe alongside it, and app/services/audio.py resolves both
# from PATH with no configurable fallback: without them every voice check-in
# fails. ca-certificates and tzdata already ship in the slim images, named
# here so an upstream change cannot quietly break TLS to Neon or the
# America/Toronto lookup in app/core/timeutil.py.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        ffmpeg \
        tzdata; \
    rm -rf /var/lib/apt/lists/*

# No TZ is set on purpose. CI runs in UTC and caught a timezone bug this
# machine hid, so production stays UTC too and timeutil does the converting.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Left root owned: the process serving traffic has no business rewriting its
# own code. Both stages use the same base image and the same venv path,
# because the venv's console scripts carry absolute shebangs.
COPY --from=builder /app/.venv ./.venv

# alembic.ini and alembic/ live outside the app package, so they are absent
# from a wheel and have to be copied by hand. They sit next to the source
# because alembic.ini resolves its script location relative to itself.
# scripts/ is deliberately absent: those are one-time local helpers that
# write into backend/.env.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh

RUN useradd --create-home --uid 10001 aimentum
USER aimentum

# Fail the build, not the 7am push, when something the app needs at runtime
# did not make it into the image. Run as the unprivileged user so this also
# proves that user can read everything it needs. Importing app.main is safe
# with no database: every setting has a default and the engine is lazy.
RUN set -eux; \
    ffmpeg -version > /dev/null; \
    ffprobe -version > /dev/null; \
    python -c "from zoneinfo import ZoneInfo; ZoneInfo('America/Toronto')"; \
    python -c "import app.main"; \
    python -c "import app.services.llm as m; assert list(m.PROMPTS_DIR.glob('*.txt')), m.PROMPTS_DIR"; \
    alembic heads > /dev/null

# Metadata only. Render injects PORT and the entrypoint honours it.
EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

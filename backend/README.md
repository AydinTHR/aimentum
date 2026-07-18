# Aimentum backend

FastAPI JSON API for Aimentum, the single-user AI accountability agent. The API is
client-agnostic and secured by a single bearer token. See the repository root
[README](../README.md) for the product overview and [docs/adr](../docs/adr) for the
architecture decisions.

## Run it

```bash
docker compose -f ../docker-compose.yml up -d db

uv venv --python 3.12 && uv pip install -e ".[dev]"
cp .env.example .env
uv run uvicorn app.main:app --reload    # http://localhost:8000/health
```

## Checks

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy app
uv run pytest
```

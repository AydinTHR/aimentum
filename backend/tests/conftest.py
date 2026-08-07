import os
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db import Base, get_db, get_session_factory
from app.main import app
from app.services.calendar import FakeCalendarService, get_calendar
from app.services.llm import get_llm
from app.services.push import FakePushTransport, get_push_transport
from app.services.stt import FakeSpeechToText, get_stt
from tests.agent_fakes import FakeLlm

TEST_TOKEN = "test-token"
TEST_TICK_SECRET = "test-tick-secret"
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A dedicated database so tests can never touch development data. The schema
# is built by running the real Alembic migrations, so every test run also
# verifies that the migration chain actually produces the model schema.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://aimentum:aimentum@localhost:5432/aimentum_test",
)


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "db", "postgres"}


def _guard_destructive(url_str: str) -> None:
    """Refuse to drop the schema of a database that is not local.

    The suite wipes and rebuilds its schema on every run. Development now
    points at a hosted database, so a stray TEST_DATABASE_URL is the
    difference between a test run and losing real data. Set
    ALLOW_REMOTE_TEST_DB=1 to override, for a throwaway branch.
    """
    host = make_url(url_str).host or ""
    if host in LOCAL_HOSTS or os.environ.get("ALLOW_REMOTE_TEST_DB") == "1":
        return
    raise RuntimeError(
        f"refusing to run destructive tests against non-local host {host!r}. "
        "Point TEST_DATABASE_URL at a local Postgres, or set "
        "ALLOW_REMOTE_TEST_DB=1 if this really is a throwaway database."
    )


def _ensure_database(url_str: str) -> None:
    url = make_url(url_str)
    admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin_engine.dispose()


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    _guard_destructive(TEST_DATABASE_URL)
    _ensure_database(TEST_DATABASE_URL)
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    alembic_cfg = AlembicConfig(os.path.join(BACKEND_DIR, "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(alembic_cfg, "head")
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def _secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_token", TEST_TOKEN)
    monkeypatch.setattr(settings, "tick_secret", TEST_TICK_SECRET)


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def fake_calendar() -> FakeCalendarService:
    """Shared with the client fixture, so a test can seed events or take the
    calendar offline and the app sees the same instance."""
    return FakeCalendarService()


@pytest.fixture
def client(db_session: Session, fake_calendar: FakeCalendarService) -> Iterator[TestClient]:
    def override() -> Iterator[Session]:
        yield db_session

    @contextmanager
    def override_factory() -> Iterator[Session]:
        # Background tasks get the same session as the request, and must not
        # close it: the fixture owns its lifetime.
        yield db_session

    app.dependency_overrides[get_db] = override
    app.dependency_overrides[get_session_factory] = lambda: override_factory
    # Always faked: no test should ever reach for real Google credentials.
    app.dependency_overrides[get_calendar] = lambda: fake_calendar
    with TestClient(app) as test_client:
        test_client.headers.update({"Authorization": f"Bearer {TEST_TOKEN}"})
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def fake_push() -> Iterator[FakePushTransport]:
    fake = FakePushTransport()
    app.dependency_overrides[get_push_transport] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_push_transport, None)


@pytest.fixture
def fake_llm() -> Iterator[FakeLlm]:
    fake = FakeLlm()
    app.dependency_overrides[get_llm] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_llm, None)


@pytest.fixture
def fake_stt() -> Iterator[FakeSpeechToText]:
    fake = FakeSpeechToText()
    app.dependency_overrides[get_stt] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_stt, None)

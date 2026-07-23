import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from alembic.config import Config as AlembicConfig
from app.core.config import settings
from app.db import Base, get_db
from app.main import app

TEST_TOKEN = "test-token"
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A dedicated database so tests can never touch development data. The schema
# is built by running the real Alembic migrations, so every test run also
# verifies that the migration chain actually produces the model schema.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://aimentum:aimentum@localhost:5432/aimentum_test",
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
def _app_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_token", TEST_TOKEN)


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
def client(db_session: Session) -> Iterator[TestClient]:
    def override() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as test_client:
        test_client.headers.update({"Authorization": f"Bearer {TEST_TOKEN}"})
        yield test_client
    app.dependency_overrides.clear()

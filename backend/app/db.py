from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    # pool_pre_ping because both halves of the hosting go to sleep: Neon
    # suspends an idle compute after a few minutes and Render spins the
    # service down after longer, which leaves a window where the pool still
    # holds connections the database has already closed. Without the ping the
    # first request in that window dies on a closed socket, and /health
    # touches no database so nothing upstream would notice.
    return create_engine(settings.database_url, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with get_sessionmaker()() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db)]

SessionFactory = Callable[[], AbstractContextManager[Session]]


@contextmanager
def session_scope() -> Iterator[Session]:
    with get_sessionmaker()() as session:
        yield session


def get_session_factory() -> SessionFactory:
    """A way to open a session outside the request cycle.

    Background tasks run after the response is sent, by which point the
    request-scoped session is closed. They take this factory instead, which
    tests override so background work lands in the test transaction.
    """
    return session_scope


SessionFactoryDep = Annotated[SessionFactory, Depends(get_session_factory)]

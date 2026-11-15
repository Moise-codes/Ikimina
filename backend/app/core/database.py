"""Database engine, session factory and declarative base.

We use synchronous SQLAlchemy 2.0 with the psycopg 3 driver. Sync is chosen
deliberately: it keeps the request path simple, works well with the blocking
psycopg driver and is easy to reason about under load.

Two invariants matter here:

* **One session per request.** ``get_db`` hands out a session and guarantees it
  is rolled back on error and always closed.
* **Stable constraint names.** ``Base`` carries a naming convention so that
  Alembic can name and later drop constraints deterministically even on
  databases that do not store names for everything (PostgreSQL is fine, but the
  convention also keeps migrations readable).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

# Deterministic constraint/index names. ``%(column_0_label)s`` is used for
# indexes so that index names do not collide across tables.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def build_engine(database_url: str) -> Engine:
    """Create a tuned engine for ``database_url``.

    ``pool_pre_ping`` protects against connections that a proxy or the database
    itself has dropped. Pool size and overflow come from settings so they can be
    tuned per environment. The engine does not open a connection until first use.
    """
    settings = get_settings()
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle_seconds,
    )


_settings = get_settings()

#: Process-wide engine used by the API and by background workers.
engine: Engine = build_engine(_settings.database_url)

#: Session factory. ``expire_on_commit=False`` lets response serialisation read
#: attributes after a commit without triggering another query; ``autoflush`` is
#: off so that flushes happen at explicit, predictable points.
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


class Base(DeclarativeBase):
    """Declarative base carrying the shared metadata and naming convention."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session.

    The session is always closed; on an exception it is rolled back first so a
    failed request cannot leave a half-finished transaction behind.
    """
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def is_database_ready() -> bool:
    """Return ``True`` if a trivial query round-trips to PostgreSQL."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True

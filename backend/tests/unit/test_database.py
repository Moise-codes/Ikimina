"""Unit tests for ``app.core.database``.

These tests never touch PostgreSQL: they assert the engine/session wiring and
the request-session lifecycle. Anything requiring a live database is an
integration test and is marked as such.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core import database
from app.core.database import NAMING_CONVENTION, Base, build_engine, get_db


class FakeSession:
    """Stand-in for ``Session`` recording lifecycle calls."""

    def __init__(self) -> None:
        self.closed = False
        self.rolled_back = False

    def close(self) -> None:
        self.closed = True

    def rollback(self) -> None:
        self.rolled_back = True


def test_naming_convention_is_applied_to_base_metadata() -> None:
    assert Base.metadata.naming_convention == NAMING_CONVENTION
    assert set(NAMING_CONVENTION) == {"ix", "uq", "ck", "fk", "pk"}


def test_build_engine_returns_tuned_postgres_engine() -> None:
    engine = build_engine("postgresql+psycopg://user:pw@localhost:5432/ikimina")

    assert isinstance(engine, Engine)
    assert engine.dialect.name == "postgresql"
    # Connections that a proxy or the server has dropped are detected before use.
    assert engine.pool._pre_ping is True


def test_module_session_factory_is_configured() -> None:
    assert isinstance(database.engine, Engine)
    assert isinstance(database.SessionLocal, sessionmaker)
    # sessionmaker exposes an anonymous subclass of Session.
    assert issubclass(database.SessionLocal.class_, Session)
    # Autoflush off and attributes usable after commit: see module docstring.
    assert database.SessionLocal.kw["autoflush"] is False
    assert database.SessionLocal.kw["expire_on_commit"] is False


def test_get_db_yields_a_session_and_always_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSession()
    monkeypatch.setattr(database, "SessionLocal", lambda: fake)

    dependency: Iterator[Session] = get_db()
    assert next(dependency) is fake
    dependency.close()

    assert fake.closed is True
    assert fake.rolled_back is False


def test_get_db_rolls_back_and_reraises_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSession()
    monkeypatch.setattr(database, "SessionLocal", lambda: fake)

    dependency: Iterator[Session] = get_db()
    next(dependency)

    with pytest.raises(RuntimeError, match="boom"):
        dependency.throw(RuntimeError("boom"))

    assert fake.rolled_back is True
    assert fake.closed is True

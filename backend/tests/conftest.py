"""Shared pytest configuration.

Environment variables are set *before* any application module is imported, so
``Settings`` validation succeeds in a clean checkout (for example in CI) without
depending on a developer's local ``.env``. Every value here is a throw-away test
value; real secrets never live in the test suite.

The secrets are forced (not ``setdefault``) so a misconfigured local ``.env``
can never make the suite behave differently on another machine. The connection
URLs are derived so that tests always talk to the **test** database and a
separate Redis database, whether the values come from a developer's ``.env`` or
from CI service configuration.
"""

from __future__ import annotations

import base64
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import pytest
from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Load the developer's .env (if any) without overriding anything already in the
# environment. In CI there is no .env, so the fallbacks below apply.
load_dotenv(_REPO_ROOT / ".env", override=False)

os.environ["ENVIRONMENT"] = "local"

# Deterministic, obviously-fake secrets that still satisfy validation.
os.environ["SECRET_KEY"] = "test-only-secret-key-that-is-definitely-long-enough-000"
os.environ["ENCRYPTION_KEY"] = base64.urlsafe_b64encode(b"0" * 32).decode()

_DEFAULT_DATABASE_URL = "postgresql+psycopg://ikimina:ikimina@localhost:5432/ikimina_test"
_DEFAULT_REDIS_URL = "redis://localhost:6379/15"


def _with_database(url: str, database: str) -> str:
    """Return ``url`` pointing at ``database`` instead of its current one."""
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{database}"))


def _with_redis_db(url: str, index: int) -> str:
    """Return ``url`` backed by Redis database ``index`` (keeps auth/host/port)."""
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{index}"))


_test_database = os.environ.get("POSTGRES_TEST_DB", "ikimina_test")
_base_database_url = os.environ.get("DATABASE_URL")
os.environ["DATABASE_URL"] = (
    _with_database(_base_database_url, _test_database)
    if _base_database_url
    else _DEFAULT_DATABASE_URL
)

_base_redis_url = os.environ.get("REDIS_URL")
os.environ["REDIS_URL"] = (
    _with_redis_db(_base_redis_url, 15) if _base_redis_url else _DEFAULT_REDIS_URL
)


@pytest.fixture
def make_settings() -> Callable[..., Any]:
    """Return a factory building ``Settings`` from a known-good baseline."""
    from app.core.config import Settings

    baseline: dict[str, object] = {
        "secret_key": "t" * 40,
        "encryption_key": base64.urlsafe_b64encode(b"0" * 32).decode(),
        "database_url": "postgresql+psycopg://ikimina:pw@localhost:5432/ikimina",
        "redis_url": "redis://:pw@localhost:6379/0",
    }

    def _make(**overrides: object) -> Any:
        values = {**baseline, **overrides}
        return Settings(_env_file=None, **values)

    return _make

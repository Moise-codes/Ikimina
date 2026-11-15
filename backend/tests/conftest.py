"""Shared pytest configuration.

Environment variables are set *before* any application module is imported, so
``Settings`` validation succeeds in a clean checkout (for example in CI) without
depending on a developer's local ``.env``. Every value here is a throw-away test
value; real secrets never live in the test suite.

The secrets are forced (not ``setdefault``) so a misconfigured local ``.env``
can never make the suite behave differently on another machine. The connection
URLs use ``setdefault`` so a real ``.env`` or CI service configuration wins.
"""

from __future__ import annotations

import base64
import os
from collections.abc import Callable
from typing import Any

import pytest

os.environ["ENVIRONMENT"] = "local"

# Deterministic, obviously-fake secrets that still satisfy validation.
os.environ["SECRET_KEY"] = "test-only-secret-key-that-is-definitely-long-enough-000"
os.environ["ENCRYPTION_KEY"] = base64.urlsafe_b64encode(b"0" * 32).decode()

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ikimina:ikimina@localhost:5432/ikimina_test",
)
os.environ.setdefault("REDIS_URL", "redis://:ikimina@localhost:6379/15")


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

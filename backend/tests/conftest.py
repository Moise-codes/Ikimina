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

os.environ["ENVIRONMENT"] = "local"

# Deterministic, obviously-fake secrets that still satisfy validation.
os.environ["SECRET_KEY"] = "test-only-secret-key-that-is-definitely-long-enough-000"
os.environ["ENCRYPTION_KEY"] = base64.urlsafe_b64encode(b"0" * 32).decode()

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ikimina:ikimina@localhost:5432/ikimina_test",
)
os.environ.setdefault("REDIS_URL", "redis://:ikimina@localhost:6379/15")

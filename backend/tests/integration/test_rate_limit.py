"""Sliding-window rate limiter tests (require a running Redis)."""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator

import pytest

from app.core.errors import AppError
from app.core.ratelimit import RateLimiter, RateLimitRule
from app.core.redis import redis_client

pytestmark = pytest.mark.integration


@pytest.fixture
def limiter() -> Iterator[RateLimiter]:
    instance = RateLimiter(redis_client)
    yield instance
    for key in redis_client.scan_iter("ratelimit:test:*"):
        redis_client.delete(key)


def _scope() -> str:
    return f"test:{uuid.uuid4().hex}"


def test_allows_up_to_the_limit(limiter: RateLimiter) -> None:
    rule = RateLimitRule(limit=3, window_seconds=60)
    scope = _scope()
    for _ in range(3):
        limiter.check(scope=scope, identifier="user", rule=rule)


def test_rejects_once_over_the_limit(limiter: RateLimiter) -> None:
    rule = RateLimitRule(limit=2, window_seconds=60)
    scope = _scope()
    limiter.check(scope=scope, identifier="user", rule=rule)
    limiter.check(scope=scope, identifier="user", rule=rule)

    with pytest.raises(AppError) as excinfo:
        limiter.check(scope=scope, identifier="user", rule=rule)

    error = excinfo.value
    assert error.status_code == 429
    assert error.code == "rate_limited"
    assert error.headers is not None
    assert int(error.headers["Retry-After"]) >= 1


def test_identifiers_are_independent(limiter: RateLimiter) -> None:
    rule = RateLimitRule(limit=1, window_seconds=60)
    scope = _scope()
    limiter.check(scope=scope, identifier="alice", rule=rule)
    # A different identifier has its own budget.
    limiter.check(scope=scope, identifier="bob", rule=rule)


def test_scopes_are_independent(limiter: RateLimiter) -> None:
    rule = RateLimitRule(limit=1, window_seconds=60)
    identifier = "user"
    limiter.check(scope=_scope(), identifier=identifier, rule=rule)
    limiter.check(scope=_scope(), identifier=identifier, rule=rule)


def test_window_expiry_allows_again(limiter: RateLimiter) -> None:
    rule = RateLimitRule(limit=1, window_seconds=1)
    scope = _scope()
    limiter.check(scope=scope, identifier="user", rule=rule)
    with pytest.raises(AppError):
        limiter.check(scope=scope, identifier="user", rule=rule)

    time.sleep(1.2)
    limiter.check(scope=scope, identifier="user", rule=rule)

"""Tests for ``RateLimitRule`` validation (no Redis needed)."""

from __future__ import annotations

import pytest

from app.core.ratelimit import RateLimitRule


@pytest.mark.unit
def test_valid_rule() -> None:
    rule = RateLimitRule(limit=5, window_seconds=60)
    assert rule.limit == 5
    assert rule.window_seconds == 60


@pytest.mark.unit
@pytest.mark.parametrize(("limit", "window"), [(0, 60), (-1, 60), (5, 0), (5, -1)])
def test_invalid_rule_is_rejected(limit: int, window: int) -> None:
    with pytest.raises(ValueError):
        RateLimitRule(limit=limit, window_seconds=window)


@pytest.mark.unit
def test_rule_is_hashable_and_frozen() -> None:
    rule = RateLimitRule(limit=5, window_seconds=60)
    assert hash(rule)
    with pytest.raises(AttributeError):
        rule.limit = 10  # type: ignore[misc]

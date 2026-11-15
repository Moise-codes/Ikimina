"""Tests for the IP-scoped rate-limit dependency (no Redis needed)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.core import ratelimit
from app.core.ratelimit import RateLimitRule, client_ip, ip_rate_limit


def _request(host: str | None) -> Any:
    client = SimpleNamespace(host=host) if host is not None else None
    return SimpleNamespace(client=client)


@pytest.mark.unit
def test_client_ip_returns_the_socket_address() -> None:
    assert client_ip(_request("203.0.113.7")) == "203.0.113.7"


@pytest.mark.unit
def test_client_ip_falls_back_when_unknown() -> None:
    assert client_ip(_request(None)) == "unknown"
    assert client_ip(_request("")) == "unknown"


@pytest.mark.unit
def test_ip_rate_limit_records_a_hit_for_the_client_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[tuple[str, str, RateLimitRule]] = []

    class Recorder:
        def check(self, *, scope: str, identifier: str, rule: RateLimitRule) -> None:
            recorded.append((scope, identifier, rule))

    monkeypatch.setattr(ratelimit, "rate_limiter", Recorder())

    rule = RateLimitRule(limit=5, window_seconds=60)
    dependency = ip_rate_limit("login", rule)
    dependency(_request("198.51.100.4"))

    assert recorded == [("login", "198.51.100.4", rule)]

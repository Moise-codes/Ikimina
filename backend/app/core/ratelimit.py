"""Redis-backed rate limiting.

A **sliding window** counter per key, implemented with a sorted set: every hit
is a member scored by its timestamp, hits older than the window are trimmed, and
the remaining members are counted. Compared with a fixed window this avoids the
"two windows' worth of traffic at the boundary" burst.

The trim-count-record sequence runs as a single Lua script, so it is atomic and
two concurrent requests can never both squeeze past the limit.

The limiter is deliberately fail-closed: if Redis is unreachable the exception
propagates (a 500 for the request) rather than silently allowing unlimited
traffic on an abuse-sensitive route.
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from fastapi import Request
from redis import Redis

from app.core.errors import AppError
from app.core.redis import redis_client

#: Returns {allowed, retry_after_seconds}. ``now``/``window`` are seconds.
_SLIDING_WINDOW_LUA: Final[str] = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = window
    if oldest[2] then
        retry_after = math.ceil(window - (now - tonumber(oldest[2])))
    end
    return {0, retry_after}
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, math.ceil(window))
return {1, 0}
"""


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    """A single ``limit`` requests per ``window_seconds`` allowance."""

    limit: int
    window_seconds: int

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValueError("limit must be at least 1")
        if self.window_seconds < 1:
            raise ValueError("window_seconds must be at least 1")


class RateLimiter:
    """Counts hits in Redis and rejects those over the limit."""

    def __init__(self, client: Redis, *, prefix: str = "ratelimit") -> None:
        self._client = client
        self._prefix = prefix
        self._script = client.register_script(_SLIDING_WINDOW_LUA)

    def check(self, *, scope: str, identifier: str, rule: RateLimitRule) -> None:
        """Record a hit for ``identifier`` in ``scope``.

        Raises:
            AppError: HTTP 429 with a ``Retry-After`` header when the limit for
                the current window has already been reached.
        """
        key = f"{self._prefix}:{scope}:{identifier}"
        now = time.time()
        # A unique member per hit so simultaneous requests do not collide.
        member = f"{now}:{secrets.token_hex(4)}"
        allowed, retry_after = self._script(
            keys=[key],
            args=[str(now), str(rule.window_seconds), str(rule.limit), member],
        )
        if not allowed:
            raise AppError(
                status_code=429,
                code="rate_limited",
                message="Too many requests; please try again later",
                headers={"Retry-After": str(int(retry_after))},
            )


#: Process-wide limiter bound to the shared Redis client.
rate_limiter = RateLimiter(redis_client)


def client_ip(request: Request) -> str:
    """Best-effort client address for IP-scoped limits."""
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


def ip_rate_limit(scope: str, rule: RateLimitRule) -> Callable[[Request], None]:
    """Build a FastAPI dependency that rate-limits by client IP.

    Usage::

        @router.post("/login", dependencies=[Depends(ip_rate_limit("login", RULE))])
    """

    def dependency(request: Request) -> None:
        rate_limiter.check(scope=scope, identifier=client_ip(request), rule=rule)

    return dependency

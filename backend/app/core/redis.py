"""Shared Redis client and a readiness check.

Redis backs rate limiting, login lockouts and short-lived OTP state. The client
is created once per process; ``Redis.from_url`` does not open a connection until
the first command, so importing this module is cheap.
"""

from __future__ import annotations

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

_settings = get_settings()

#: Process-wide Redis client (decode_responses so values come back as ``str``).
redis_client: Redis = Redis.from_url(_settings.redis_url, decode_responses=True)


def is_redis_ready() -> bool:
    """Return ``True`` if Redis answers ``PING`` within the client timeout."""
    try:
        return bool(redis_client.ping())
    except RedisError:
        return False

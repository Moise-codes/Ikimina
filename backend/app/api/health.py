"""Operational probes.

``/health`` is a liveness probe: it answers as long as the process is running and
deliberately checks no dependencies, so a briefly unavailable database never gets
a healthy process killed.

``/ready`` is a readiness probe: it verifies the database and Redis are
reachable and returns 503 (with the standard error envelope) when they are not,
so a load balancer stops sending traffic to this instance.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.database import is_database_ready
from app.core.errors import AppError
from app.core.redis import is_redis_ready

router = APIRouter(tags=["ops"])


@router.get("/health", summary="Liveness probe")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe")
def ready() -> dict[str, str]:
    unreachable = [
        name
        for name, check in (("database", is_database_ready), ("redis", is_redis_ready))
        if not check()
    ]
    if unreachable:
        raise AppError(
            status_code=503,
            code="service_unavailable",
            message=f"Service not ready: {', '.join(unreachable)} unreachable",
        )
    return {"status": "ready"}

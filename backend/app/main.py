"""Application factory.

``create_app`` assembles one FastAPI application from configuration and an
explicit middleware stack. This is the single place that knows the ordering of
middleware, where routers are mounted and whether the interactive docs are
exposed. Tests build apps with a chosen ``Settings`` instance instead of
mutating the process environment.

Middleware order (outermost first):
    1. RequestID      - assign/echo X-Request-ID, set it on request.state
    2. SecurityHeaders- add security headers to every response
    3. TrustedHost    - reject requests with an unexpected Host header
    4. CORS           - browser cross-origin rules
    5. BodySizeLimit  - reject oversized bodies before they are read
Starlette applies user middleware in the reverse of the order added, so the
outermost middleware is added last (see ``_add_middleware``).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.middleware import (
    MAX_REQUEST_BODY_BYTES,
    BodySizeLimitMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
    security_headers,
)

#: Methods and headers the browser is allowed to use, listed explicitly because
#: wildcards must not be combined with credentials (see the settings validator).
_ALLOWED_METHODS = ["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"]
_ALLOWED_HEADERS = ["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"]


def _add_middleware(app: FastAPI, settings: Settings) -> None:
    # Added inner-first: Starlette wraps in reverse, so the last one added ends
    # up outermost.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_REQUEST_BODY_BYTES)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=_ALLOWED_METHODS,
            allow_headers=_ALLOWED_HEADERS,
            expose_headers=["X-Request-ID"],
            max_age=600,
        )
    if settings.trusted_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
    app.add_middleware(SecurityHeadersMiddleware, headers=security_headers(settings.is_production))
    app.add_middleware(RequestIDMiddleware)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return the FastAPI application."""
    settings = settings or get_settings()
    expose_docs = settings.expose_docs

    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        docs_url="/docs" if expose_docs else None,
        redoc_url="/redoc" if expose_docs else None,
        openapi_url="/openapi.json" if expose_docs else None,
    )

    register_exception_handlers(app)
    _add_middleware(app, settings)

    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


#: The application object imported by ASGI servers (``uvicorn app.main:app``).
app = create_app()

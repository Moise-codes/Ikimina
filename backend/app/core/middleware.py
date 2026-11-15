"""ASGI middleware: request ids, security headers and a body-size limit.

These are written as raw ASGI middleware (not ``BaseHTTPMiddleware``) so they
add no per-request task overhead and can wrap the response without buffering it.
"""

from __future__ import annotations

import re
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_body

#: Largest request body we accept (1 MiB). Money/JSON payloads are tiny; this
#: stops trivially large uploads from consuming memory before validation runs.
MAX_REQUEST_BODY_BYTES = 1_048_576

#: Incoming request ids must be short and made of safe characters, otherwise we
#: generate our own (an attacker must not be able to inject log content).
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _clean_request_id(value: str | None) -> str | None:
    if value and _REQUEST_ID_PATTERN.match(value):
        return value
    return None


def security_headers(is_production: bool) -> dict[str, str]:
    """Return the security headers applied to every response.

    HSTS is only sent in production, where the API is served over HTTPS behind a
    TLS-terminating proxy; sending it in local development would break plain
    HTTP access to localhost.
    """
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-site",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        # This API only ever returns JSON, so nothing needs to be loadable.
        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    }
    if is_production:
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return headers


def _scope_request_id(scope: Scope) -> str:
    state = scope.setdefault("state", {})
    return str(state.get("request_id", ""))


class RequestIDMiddleware:
    """Assign a request id, expose it on ``request.state`` and echo it back."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get("x-request-id")
        request_id = _clean_request_id(incoming) or str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        await self.app(scope, receive, send_with_request_id)


class SecurityHeadersMiddleware:
    """Add the configured security headers to every response."""

    def __init__(self, app: ASGIApp, headers: dict[str, str]) -> None:
        self.app = app
        self.headers = headers

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message).update(self.headers)
            await send(message)

        await self.app(scope, receive, send_with_security_headers)


class BodySizeLimitMiddleware:
    """Reject requests whose ``Content-Length`` exceeds ``max_bytes``.

    Uses the declared length only; a chunked request without a length is streamed
    to the app (JSON bodies are small, so this is an acceptable trade-off and
    avoids buffering the whole body here).
    """

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = Headers(scope=scope).get("content-length")
        if content_length is not None:
            try:
                length = int(content_length)
            except ValueError:
                length = None
            if length is not None and length > self.max_bytes:
                response = JSONResponse(
                    status_code=413,
                    content=error_body(
                        code="payload_too_large",
                        message=f"Request body exceeds the {self.max_bytes} byte limit",
                        request_id=_scope_request_id(scope),
                    ),
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)

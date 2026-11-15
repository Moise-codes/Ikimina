"""Standard error envelope and exception handlers.

Every error the API returns — whether it comes from a validation failure, an
``HTTPException``, a domain error we raise ourselves, or an unexpected crash —
uses one shape::

    {"error": {"code": ..., "message": ..., "request_id": ...}}

Clients can therefore handle errors uniformly and support can quote the
``request_id`` to find the matching log line.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

#: Fallback code for any unhandled server error.
INTERNAL_ERROR_CODE = "internal_error"

#: Human-readable, stable code for each HTTP status we map explicitly.
_HTTP_STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
    503: "service_unavailable",
}


class AppError(Exception):
    """A domain or application error that maps to a known HTTP status/code.

    Raise this from anywhere in the request path to produce the standard error
    envelope with a meaningful status and code.
    """

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers


def request_id_of(request: Request) -> str:
    """Return the request id assigned by the request-id middleware (or "")."""
    return str(getattr(request.state, "request_id", ""))


def error_body(*, code: str, message: str, request_id: str, details: Any = None) -> dict[str, Any]:
    """Build the standard error envelope."""
    error: dict[str, Any] = {"code": code, "message": message, "request_id": request_id}
    if details is not None:
        error["details"] = details
    return {"error": error}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the handlers that produce the standard error envelope."""

    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(
                code=exc.code, message=exc.message, request_id=request_id_of(request)
            ),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_body(
                code="validation_error",
                message="Request validation failed",
                request_id=request_id_of(request),
                details=jsonable_encoder(exc.errors()),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_STATUS_CODES.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code=code, message=message, request_id=request_id_of(request)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # The message is deliberately generic: internal details must never leak.
        # Phase 8 adds structured logging that records the traceback here.
        return JSONResponse(
            status_code=500,
            content=error_body(
                code=INTERNAL_ERROR_CODE,
                message="An unexpected error occurred",
                request_id=request_id_of(request),
            ),
        )

"""Tests for the standard error envelope and its handlers."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.errors import AppError, register_exception_handlers
from app.core.middleware import RequestIDMiddleware


def _error_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/app-error")
    def app_error() -> None:
        raise AppError(status_code=409, code="conflict", message="already exists")

    @app.get("/http-error")
    def http_error() -> None:
        raise HTTPException(status_code=403, detail="forbidden by policy")

    @app.get("/validate")
    def validate(value: int) -> dict[str, int]:
        return {"value": value}

    @app.get("/crash")
    def crash() -> None:
        raise RuntimeError("kaboom")

    return app


def test_app_error_uses_envelope() -> None:
    response = TestClient(_error_app()).get("/app-error")

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "conflict"
    assert error["message"] == "already exists"
    assert error["request_id"]


def test_http_exception_maps_status_to_code() -> None:
    response = TestClient(_error_app()).get("/http-error")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_not_found_uses_envelope() -> None:
    response = TestClient(_error_app()).get("/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_validation_error_uses_envelope_with_details() -> None:
    response = TestClient(_error_app()).get("/validate", params={"value": "not-an-int"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert isinstance(error["details"], list)
    assert error["details"]


def test_unexpected_error_is_generic_500_without_leaking_details() -> None:
    client = TestClient(_error_app(), raise_server_exceptions=False)

    response = client.get("/crash")

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "internal_error"
    assert "kaboom" not in error["message"]

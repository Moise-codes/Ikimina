"""Tests for the application factory, middleware stack and probes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import health as health_module
from app.core.middleware import MAX_REQUEST_BODY_BYTES, security_headers
from app.main import app, create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def build_app(make_settings: Callable[..., Any], **overrides: object) -> TestClient:
    return TestClient(create_app(make_settings(**overrides)))


# --- Probes ------------------------------------------------------------------


def test_health_does_not_touch_dependencies(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_ok_when_dependencies_reachable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(health_module, "is_database_ready", lambda: True)
    monkeypatch.setattr(health_module, "is_redis_ready", lambda: True)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@pytest.mark.parametrize("down", ["database", "redis"])
def test_ready_returns_503_envelope_when_dependency_down(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, down: str
) -> None:
    monkeypatch.setattr(health_module, "is_database_ready", lambda: down != "database")
    monkeypatch.setattr(health_module, "is_redis_ready", lambda: down != "redis")

    response = client.get("/ready")

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "service_unavailable"
    assert down in error["message"]
    assert error["request_id"]


# --- Request id --------------------------------------------------------------


def test_request_id_is_generated_and_echoed(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["X-Request-ID"]


def test_client_supplied_request_id_is_honoured(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "abc-123"})

    assert response.headers["X-Request-ID"] == "abc-123"


@pytest.mark.parametrize("unsafe", ["bad id", "x" * 200, "id!with<punct>"])
def test_unsafe_request_id_is_replaced(client: TestClient, unsafe: str) -> None:
    response = client.get("/health", headers={"X-Request-ID": unsafe})

    assert response.headers["X-Request-ID"] != unsafe


# --- Security headers --------------------------------------------------------


def test_security_headers_are_applied(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "Content-Security-Policy" in response.headers
    # HSTS is production-only.
    assert "Strict-Transport-Security" not in response.headers


def test_hsts_is_added_only_in_production() -> None:
    assert "Strict-Transport-Security" in security_headers(is_production=True)
    assert "Strict-Transport-Security" not in security_headers(is_production=False)


# --- Body size limit ---------------------------------------------------------


def test_oversized_body_is_rejected_with_envelope(client: TestClient) -> None:
    response = client.post(
        "/health",
        content="x" * (MAX_REQUEST_BODY_BYTES + 1),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
    assert response.headers["X-Request-ID"]


# --- Error envelope ----------------------------------------------------------


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["request_id"]


# --- Docs exposure -----------------------------------------------------------


def test_docs_exposed_in_local(make_settings: Callable[..., Any]) -> None:
    application = create_app(make_settings(environment="local"))

    assert application.docs_url == "/docs"
    assert application.openapi_url == "/openapi.json"


def test_docs_hidden_in_production(make_settings: Callable[..., Any]) -> None:
    application = create_app(make_settings(environment="production"))

    assert application.docs_url is None
    assert application.redoc_url is None
    assert application.openapi_url is None


# --- CORS and trusted hosts --------------------------------------------------


def test_cors_preflight_allows_configured_origin(make_settings: Callable[..., Any]) -> None:
    with build_app(make_settings, cors_origins="http://localhost:3000") as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_untrusted_host_is_rejected(make_settings: Callable[..., Any]) -> None:
    with build_app(make_settings, trusted_hosts="example.com") as client:
        response = client.get("/health", headers={"Host": "evil.test"})

    assert response.status_code == 400

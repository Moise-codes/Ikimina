"""Smoke test proving the test harness (pytest + httpx TestClient) works.

This is intentionally tiny. It will be replaced by real endpoint tests as the
application factory is built in Phase 0 task 6.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_package_imports_and_health_responds() -> None:
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

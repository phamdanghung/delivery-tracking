from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app import health
from app.main import app


def test_liveness_independent_of_dependencies():
    with TestClient(app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    UUID(response.headers["x-request-id"])


@pytest.mark.parametrize("failed", [None, "database", "redis", "storage", "traccar"])
def test_readiness_checks_every_dependency(monkeypatch, failed):
    calls = []
    for name in ("database", "redis", "storage", "traccar"):

        def check(settings, dependency=name):
            calls.append(dependency)
            if dependency == failed:
                raise RuntimeError("secret password must never be returned")

        monkeypatch.setattr(health, f"check_{name}", check)
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == (503 if failed else 200)
    assert sorted(calls) == ["database", "redis", "storage", "traccar"]
    assert response.json()["checks"] == {name: name != failed for name in calls}
    assert "password" not in response.text


def test_business_routes_are_not_exposed_in_m0():
    paths = app.openapi()["paths"]
    assert set(paths) == {"/health/live", "/health/ready"}


def test_cors_allows_only_configured_origin():
    with TestClient(app) as client:
        accepted = client.get("/health/live", headers={"Origin": "http://localhost:3000"})
        rejected = client.get("/health/live", headers={"Origin": "https://untrusted.example"})
    assert accepted.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in rejected.headers

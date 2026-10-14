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


def test_only_authorized_m6_business_routes_are_exposed():
    paths = app.openapi()["paths"]
    assert "/api/v1/vehicles" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/deliveries" in paths
    assert "/api/v1/trips" in paths
    assert "/api/v1/trips/{trip_id}/optimize" in paths
    assert not any(name in path for path in paths for name in ("fuel", "commands"))
    assert "/api/v1/public/tracking/{token}" in paths
    assert "/api/v1/tracking-links" in paths
    assert "/api/v1/deliveries/{delivery_id}/pod/photos" in paths


def test_cors_allows_only_configured_origin():
    with TestClient(app) as client:
        accepted = client.get("/health/live", headers={"Origin": "http://localhost:3000"})
        rejected = client.get("/health/live", headers={"Origin": "https://untrusted.example"})
    assert accepted.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in rejected.headers

import json
import logging

import pytest
from test_m1_api import context as context

from app.config import Settings
from app.deployment_policy import enforce_production_config, production_config_issues, public_https
from app.main import JsonFormatter, logger


@pytest.mark.parametrize(
    "url",
    [
        "http://fleet.example.com",
        "https://localhost",
        "https://127.0.0.1",
        "https://[::1]",
        "https://10.0.0.1",
        "https://fleet.internal",
        "https://user:secret@fleet.example.com",
        "https://*.example.com",
        "https://fleet.example.com?token=secret",
        "https://fleet.example.com:bad",
        "https://localhost.",
        "https://127.1",
        "https://0x7f.0.0.1",
        "https://fleet.example.com:0",
        "https://fleet.example.com\n",
        "https://fleet。internal",
        "https://fleet．local",
    ],
)
def test_production_public_urls_reject_plaintext_local_credentials_and_wildcards(url):
    assert not public_https(url)


def test_production_fails_closed_but_local_and_test_are_unchanged():
    settings = Settings(_env_file=None, app_env="production", jwt_secret="secret")
    with pytest.raises(RuntimeError) as caught:
        enforce_production_config(settings)
    assert "JWT_SECRET_TOO_SHORT" in str(caught.value)
    assert "localhost" not in str(caught.value)
    assert "secret" not in str(caught.value)
    for env in ("local", "test"):
        enforce_production_config(Settings(_env_file=None, app_env=env))


def test_config_checks_are_necessary_but_not_production_acceptance():
    settings = Settings(
        _env_file=None,
        app_env="production",
        jwt_secret="a" * 32,
        database_url="postgresql://deployment/configured",
        s3_access_key="configured",
        s3_secret_key="configured",
        s3_public_endpoint_url="https://objects.fleet.example.com",
        tracking_public_base_url="https://fleet.example.com",
        cors_origins=["https://fleet.example.com"],
    )
    assert production_config_issues(settings) == []
    enforce_production_config(settings)
    assert not public_https("https://fleet.example.com/path", origin=True)


@pytest.mark.integration
def test_auth_error_and_fleet_responses_are_not_cacheable(context):
    client = context[0]
    for path in ("/api/v1/vehicles", "/api/v1/auth/me", "/api/v1/expenses"):
        response = client.get(path)
        assert response.status_code == 401
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"


@pytest.mark.integration
def test_request_logs_use_route_templates_and_never_raw_tracking_or_query(context):
    client = context[0]
    records: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = Capture()
    logger.addHandler(handler)
    try:
        response = client.get(
            "/api/v1/vehicles?token=private-query", headers={"Authorization": "Bearer private-auth"}
        )
        assert response.status_code == 401
        response = client.get("/api/v1/public/tracking/private-tracking?secret=private-query")
        assert response.status_code == 410
    finally:
        logger.removeHandler(handler)
    logs = [
        json.loads(JsonFormatter().format(r)) for r in records if r.getMessage() == "http_request"
    ]
    assert len(logs) == 2
    assert logs[1]["route_template"] == "/api/v1/public/tracking/{token}"
    for row in logs:
        assert row["request_id"] and row["duration_ms"] >= 0
        assert not any(
            secret in json.dumps(row)
            for secret in ("private-query", "private-auth", "private-tracking")
        )

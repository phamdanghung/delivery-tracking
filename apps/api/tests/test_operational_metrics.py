import json

from app.operational_metrics import p95, summarize_logs


def test_nearest_rank_percentile_and_no_samples_are_not_zero():
    assert p95([]) is None
    assert p95([float(i) for i in range(1, 101)]) == 95


def test_metrics_preserve_failures_but_never_export_raw_urls_or_payloads():
    known = {"/api/v1/trips/{trip_id}/optimize", "/api/v1/public/tracking/{token}"}
    rows = [
        {
            "message": "http_request",
            "route_template": "/api/v1/trips/{trip_id}/optimize",
            "method": "POST",
            "status_code": 422,
            "duration_ms": 123,
        },
        {
            "message": "http_request",
            "route_template": "/api/v1/public/tracking/private-secret",
            "status_code": 503,
            "duration_ms": 9,
            "password": "private-password",
        },
        {"message": "dependency_unavailable", "dependency": "redis"},
        {"message": "gps_socket_unavailable", "dependency": "traccar"},
        {"message": "http_request", "status_code": 200, "duration_ms": float("nan")},
    ]
    result = summarize_logs([json.dumps(r) for r in rows] + ["not JSON"], known)
    assert result["observed_counters"] == {
        "http_requests": 2,
        "route_optimization_error_responses": 1,
        "api_error_responses": 1,
        "dependency_unavailable_redis": 1,
        "gps_socket_unavailable": 1,
    }
    assert result["invalid_records"] == 2
    assert result["route_latency_ms"]["UNMATCHED"]["p95"] == 9
    assert "private-secret" not in json.dumps(result) and "private-password" not in json.dumps(
        result
    )
    assert result["driver_outbox_backlog"] is None
    assert "NOT_VERIFIED" in result["production_performance_acceptance"]

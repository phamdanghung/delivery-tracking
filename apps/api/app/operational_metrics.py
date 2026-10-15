"""Aggregate structured observations without preserving URLs, tokens, or payloads."""

import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any


def p95(values: list[float]) -> float | None:
    return sorted(values)[math.ceil(0.95 * len(values)) - 1] if values else None


def summarize_logs(lines: Iterable[str], allowed_routes: set[str]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    durations: dict[str, list[float]] = defaultdict(list)
    invalid = 0
    for line in lines:
        try:
            record = json.loads(line[line.index("{") :])
        except (ValueError, json.JSONDecodeError):
            invalid += 1
            continue
        if not isinstance(record, dict):
            invalid += 1
            continue
        if record.get("message") in ("gps_rest_unavailable", "gps_socket_unavailable"):
            counts[record["message"]] += 1
        if record.get("message") == "dependency_unavailable":
            dependency = record.get("dependency")
            if dependency in ("database", "redis", "storage", "traccar"):
                counts["dependency_unavailable_" + dependency] += 1
        if record.get("message") != "http_request":
            continue
        status, duration = record.get("status_code"), record.get("duration_ms")
        if (
            type(status) is not int
            or not 100 <= status <= 599
            or not isinstance(duration, (float, int))
            or isinstance(duration, bool)
            or not math.isfinite(duration)
            or duration < 0
        ):
            invalid += 1
            continue
        route = record.get("route_template")
        route = route if isinstance(route, str) and route in allowed_routes else "UNMATCHED"
        counts["http_requests"] += 1
        if status >= 500:
            counts["api_error_responses"] += 1
        if route == "/api/v1/trips/{trip_id}/optimize" and status >= 400:
            counts["route_optimization_error_responses"] += 1
        if (
            (
                "/pod/photos" in route
                or route in ("/api/v1/expense-receipts", "/api/v1/vehicle-receipts")
            )
            and record.get("method") == "POST"
            and status >= 400
        ):
            counts["upload_error_responses"] += 1
        durations[route].append(float(duration))
    return {
        "observed_counters": dict(counts),
        "invalid_records": invalid,
        "route_latency_ms": {r: {"samples": len(v), "p95": p95(v)} for r, v in durations.items()},
        "driver_outbox_backlog": None,
        "driver_outbox_backlog_reason": "Local device queues are not observable from server logs",
        "production_performance_acceptance": "NOT_VERIFIED_BY_LOG_AGGREGATION",
    }

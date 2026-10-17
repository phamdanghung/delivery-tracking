from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.reporting_telemetry import intervals, observed_report

START = datetime(2026, 10, 16, 1, tzinfo=UTC)


def point(identifier, seconds, speed=0, acc=True, valid=True):
    at = (START + timedelta(seconds=seconds)).isoformat()
    return dict(
        id=identifier,
        deviceId=1,
        latitude=10.7,
        longitude=106.7,
        fixTime=at,
        serverTime=at,
        speed=speed,
        course=0,
        valid=valid,
        attributes={"ignition": acc},
    )


class TelemetryTransport:
    """Unit transport only; not evidence of a real Traccar deployment."""

    def __init__(self, points, summary_fail=False):
        self.points = points
        self.summary_fail = summary_fail
        self.calls = []

    def get(self, endpoint, params):
        self.calls.append((endpoint, params))
        if endpoint == "positions":
            return self.points
        if self.summary_fail:
            raise HTTPException(503, "Traccar unavailable")
        return [dict(deviceId=1, startTime=params["from"], endTime=params["to"], distance=1000)]


def test_moving_idle_parked_actual_intervals_and_valid_coverage():
    provider = TelemetryTransport(
        [point(1, 0, 1), point(2, 60), point(3, 120, 0, False), point(4, 180)]
    )
    result = observed_report(provider, 1, START, START + timedelta(seconds=180))
    assert result["hours_quality"] == result["distance_quality"] == "VALID"
    assert result["operating_hours"] == Decimal(120) / 3600
    assert result["moving_hours"] == result["idle_hours"] == Decimal(60) / 3600
    assert result["distance_km"] == 1
    assert result["hours_coverage_seconds"] == 180
    assert len(result["intervals"]) == 3
    assert all("raw_points" not in p and "latitude" not in p for p in result["intervals"])


def test_gap_is_not_bridged_distance_requested_per_verified_span_only():
    provider = TelemetryTransport([point(1, 0), point(2, 60), point(3, 300), point(4, 360)])
    result = observed_report(provider, 1, START, START + timedelta(seconds=360))
    assert result["hours_quality"] == result["distance_quality"] == "PARTIAL"
    assert result["hours_coverage_seconds"] == result["distance_coverage_seconds"] == 120
    assert result["distance_km"] == 2
    summaries = [p for endpoint, p in provider.calls if endpoint == "reports/summary"]
    assert len(summaries) == 2
    assert summaries[0]["to"] == (START + timedelta(seconds=60)).isoformat()
    assert summaries[1]["from"] == (START + timedelta(seconds=300)).isoformat()


def test_missing_acc_hours_unknown_but_validated_distance_can_be_valid():
    provider = TelemetryTransport([point(1, 0, 1, None), point(2, 60, 1, None)])
    result = observed_report(provider, 1, START, START + timedelta(seconds=60))
    assert result["hours_quality"] == "UNKNOWN" and result["operating_hours"] is None
    assert result["distance_quality"] == "VALID" and result["distance_km"] == 1


@pytest.mark.parametrize(
    "points",
    [
        [],
        [point(1, 0)],
        [point(1, 0), point(2, 60, valid=False), point(3, 120)],
        [point(1, 0), point(1, 60)],
    ],
)
def test_missing_invalid_or_contradictory_observations_do_not_become_zero(points):
    result = observed_report(TelemetryTransport(points), 1, START, START + timedelta(seconds=120))
    assert result["hours_quality"] == "UNKNOWN" and result["operating_hours"] is None
    assert result["distance_quality"] == "UNKNOWN" and result["distance_km"] is None


def test_duplicate_rest_socket_fix_is_not_counted_twice_and_boundaries_not_extended():
    first, last = point(1, 20), point(2, 80)
    verified = intervals([first, first, last, last], 1, START, START + timedelta(seconds=120))
    assert len(verified) == 1 and verified[0]["seconds"] == 60
    result = observed_report(
        TelemetryTransport([first, last]), 1, START, START + timedelta(seconds=120)
    )
    assert result["hours_quality"] == "PARTIAL"
    assert result["hours_coverage_seconds"] == 60


def test_distance_source_failure_is_unknown_without_plan_or_geodesic_fallback():
    provider = TelemetryTransport([point(1, 0), point(2, 60)], summary_fail=True)
    result = observed_report(provider, 1, START, START + timedelta(seconds=60))
    assert result["hours_quality"] == "VALID"
    assert result["distance_quality"] == "UNKNOWN" and result["distance_km"] is None
    assert "TRACCAR_DISTANCE_UNAVAILABLE" in result["reasons"]


def test_unmapped_does_not_call_provider():
    provider = TelemetryTransport([])
    result = observed_report(provider, None, START, START + timedelta(seconds=60))
    assert provider.calls == []
    assert result["distance_km"] is result["operating_hours"] is None


def test_mapping_changes_use_disjoint_historical_spans_not_current_device():
    from uuid import uuid4

    from app.reporting_telemetry import mapped_report

    provider = TelemetryTransport([point(1, 0), point(2, 60), point(3, 120)])
    audit = uuid4()
    result = mapped_report(
        provider,
        [
            dict(
                id=audit,
                created_at=START + timedelta(seconds=60),
                after_json=dict(traccar_device_id=1),
            )
        ],
        START,
        START + timedelta(seconds=120),
    )
    assert result["hours_quality"] == result["distance_quality"] == "PARTIAL"
    assert result["hours_coverage_seconds"] == 60
    assert result["mapping_audit_ids"] == [audit]
    assert result["intervals"][0]["traccar_device_id"] == 1
    assert result["intervals"][0]["position_ids"] == [2, 3]
    assert "MAPPING_HISTORY_INCOMPLETE" in result["reasons"]


def test_ambiguous_mapping_history_does_not_guess_device():
    from uuid import uuid4

    from app.reporting_telemetry import mapped_report

    provider = TelemetryTransport([point(1, 0), point(2, 60)])
    result = mapped_report(
        provider,
        [dict(id=uuid4(), created_at=START, after_json=dict(traccar_device_id=d)) for d in [1, 2]],
        START,
        START + timedelta(seconds=60),
    )
    assert provider.calls == []
    assert result["operating_hours"] is result["distance_km"] is None

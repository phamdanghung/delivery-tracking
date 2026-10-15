from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.fuel_telemetry import observed_segment


def observations():
    start = datetime.now(UTC) - timedelta(minutes=10)
    end = start + timedelta(minutes=2)
    points = [
        {
            "id": i + 1,
            "deviceId": 7,
            "valid": True,
            "latitude": 10.7,
            "longitude": 106.7,
            "speed": 0,
            "course": 0,
            "fixTime": (start + timedelta(minutes=i)).isoformat(),
            "serverTime": (start + timedelta(minutes=i)).isoformat(),
            "attributes": {"ignition": True},
        }
        for i in range(3)
    ]
    report = [
        {"deviceId": 7, "distance": 0, "startTime": start.isoformat(), "endTime": end.isoformat()}
    ]
    return points, report, start, end


def test_idle_is_observed_once_not_multiplied_by_refills():
    points, report, start, end = observations()
    result = observed_segment(points, report, 7, start, end, True)
    assert result["reasons"] == []
    assert result["idle_hours"] == Decimal("2") / 60
    assert result["distance_km"] == 0
    assert result["position_ids"] == [1, 2, 3]


@pytest.mark.parametrize(
    "problem", ["invalid", "acc", "gap", "missing_distance", "nan_distance", "coverage"]
)
def test_untrustworthy_inputs_are_explicit_not_fake_zero(problem):
    points, report, start, end = observations()
    if problem == "invalid":
        points[1]["valid"] = False
    elif problem == "acc":
        points[1]["attributes"] = {}
    elif problem == "gap":
        points[-1]["fixTime"] = (end + timedelta(minutes=3)).isoformat()
        points[-1]["serverTime"] = points[-1]["fixTime"]
    elif problem == "missing_distance":
        report[0].pop("distance")
    elif problem == "nan_distance":
        report[0]["distance"] = "NaN"
    else:
        report[0]["startTime"] = end.isoformat()
    assert observed_segment(points, report, 7, start, end, True)["reasons"]


def test_no_idle_requirement_does_not_invent_missing_acc_violation():
    points, report, start, end = observations()
    for point in points:
        point["attributes"] = {}
    result = observed_segment(points, report, 7, start, end, False)
    assert result["reasons"] == []
    assert result["idle_hours"] is None
    assert result["idle_seconds"] is None
    assert result["idle_required"] is False


def test_transition_uses_existing_m1_fix_time_convention_without_extrapolation():
    points, report, start, end = observations()
    points[1]["speed"] = 10
    result = observed_segment(points, report, 7, start, end, True)
    assert result["reasons"] == []
    assert result["idle_hours"] == Decimal("1") / 60

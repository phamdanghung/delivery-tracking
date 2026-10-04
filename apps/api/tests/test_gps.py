from datetime import UTC, datetime, timedelta

import pytest

from app.gps import acc_value, engine_state, freshness, history_data, normalize

NOW = datetime(2026, 10, 5, 3, tzinfo=UTC)


@pytest.mark.parametrize(
    "age,status",
    [
        (0, "NORMAL"),
        (30, "NORMAL"),
        (30.001, "STALE"),
        (31, "STALE"),
        (120, "STALE"),
        (120.001, "LOST"),
    ],
)
def test_approved_freshness_boundaries(age, status):
    at = NOW - timedelta(seconds=age)
    assert freshness(at, at, NOW) == status


def test_delayed_old_fix_is_not_live_and_invalid_future_is_lost():
    assert freshness(NOW - timedelta(seconds=121), NOW, NOW) == "LOST"
    assert freshness(None, NOW, NOW) == "LOST"
    assert freshness(NOW + timedelta(seconds=1), NOW, NOW) == "LOST"


@pytest.mark.parametrize(
    "speed,acc,valid,expected",
    [
        (1, True, True, "MOVING"),
        (0, True, True, "IDLING"),
        (0, False, True, "PARKED"),
        (1, False, True, "UNKNOWN"),
        (1, None, True, "UNKNOWN"),
        (-1, True, True, "UNKNOWN"),
        (1, True, False, "UNKNOWN"),
        (float("nan"), True, True, "UNKNOWN"),
    ],
)
def test_acc_rule_from_locked_business(speed, acc, valid, expected):
    assert engine_state(speed, acc, valid) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        (True, True),
        (False, False),
        ("true", True),
        ("false", False),
        ("1", True),
        ("0", False),
        (None, None),
        ("unknown", None),
    ],
)
def test_acc_optional_protocol_value(raw, expected):
    assert acc_value(raw) is expected


def position(at, speed=0, acc=True, valid=True):
    return {
        "id": 1,
        "deviceId": 42,
        "valid": valid,
        "latitude": 10.7,
        "longitude": 106.7,
        "speed": speed,
        "course": 90,
        "fixTime": at.isoformat(),
        "serverTime": at.isoformat(),
        "attributes": {"ignition": acc},
    }


def test_knots_conversion_and_invalid_coordinate_not_exposed():
    result = normalize(position(NOW, speed=10), NOW)
    assert result["speed_kmh"] == 18.52
    assert result["course"] == 90
    raw = position(NOW)
    raw["latitude"] = 100
    result = normalize(raw, NOW)
    assert not result["valid"]
    assert result["latitude"] is None
    assert result["engine_state"] == "UNKNOWN"


def test_history_gap_is_not_joined_or_counted_as_stop_time():
    points = [
        position(NOW - timedelta(seconds=300)),
        position(NOW - timedelta(seconds=280)),
        position(NOW - timedelta(seconds=100)),
        position(NOW - timedelta(seconds=90)),
        position(NOW - timedelta(seconds=80), speed=2),
    ]
    result = history_data(points, NOW)
    assert len(result["segments"]) == 2
    assert len(result["gaps"]) == 1
    assert [stop["duration_seconds"] for stop in result["stops"]] == [20, 10]

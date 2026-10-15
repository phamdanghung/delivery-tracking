from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.operations_policy import (
    decimal_value,
    estimate_fuel,
    exact_variance,
    fuel_alert,
    fuel_variance,
    observed_fuel,
    outside_hours,
    safety_transition,
)


def test_real_activity_formula_includes_idling_per_vehicle_rates():
    assert estimate_fuel(Decimal("100"), Decimal("2"), Decimal("8"), Decimal("1.5")) == 11
    assert estimate_fuel(Decimal("100"), Decimal("2"), Decimal("12"), Decimal("2")) == 16


def test_profile_split_repeating_idle_hours_never_creates_false_15_percent_alert():
    first = observed_fuel(Decimal(0), Decimal(120), Decimal(8), Decimal(1))
    second = observed_fuel(Decimal(0), Decimal(120), Decimal(8), Decimal(2))
    expected = first + second
    assert decimal_value(expected) == Decimal("0.1")
    assert exact_variance(Decimal("0.115"), expected) == 15
    assert exact_variance(Decimal("0.085"), expected) == -15
    assert abs(exact_variance(Decimal("0.116"), expected)) > 15
    assert abs(exact_variance(Decimal("0.084"), expected)) > 15


@pytest.mark.parametrize(
    "actual,variance,alert",
    [
        ("11.49", "14.9", False),
        ("11.5", "15", False),
        ("11.51", "15.1", True),
        ("8.51", "-14.9", False),
        ("8.5", "-15", False),
        ("8.49", "-15.1", True),
        ("11.500001", "15.00001", True),
    ],
)
def test_absolute_variance_strict_limit_without_rounding_before_comparison(actual, variance, alert):
    assert fuel_variance(Decimal(actual), Decimal("10")) == Decimal(variance)
    assert fuel_alert(Decimal(actual), Decimal("10")) is alert


@pytest.mark.parametrize("estimated", ["0", "-1", "NaN", "Infinity"])
def test_invalid_estimate_never_produces_a_fake_variance(estimated):
    with pytest.raises(ValueError):
        fuel_variance(Decimal("1"), Decimal(estimated))


@pytest.mark.parametrize(
    "utc_time,expected",
    [("10:59:59", False), ("11:00:00", True), ("00:29:59", True), ("00:30:00", False)],
)
def test_local_outside_hours_boundaries(utc_time, expected):
    at = datetime.fromisoformat("2026-10-14T" + utc_time).replace(tzinfo=UTC)
    assert outside_hours(at) is expected


def test_missing_timezone_is_not_guessed():
    with pytest.raises(ValueError):
        outside_hours(datetime(2026, 10, 14, 18))


@pytest.mark.parametrize("old", ["NEW", "SEEN", "RESOLVED"])
@pytest.mark.parametrize("new", ["NEW", "SEEN", "RESOLVED"])
def test_three_alert_states_do_not_allow_skip_or_reverse(old, new):
    assert safety_transition(old, new) is ((old, new) in {("NEW", "SEEN"), ("SEEN", "RESOLVED")})

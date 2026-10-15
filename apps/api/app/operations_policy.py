"""Locked M7 calculations only; reconciliation periods and workflows are separate."""

from datetime import datetime, time
from decimal import Decimal, localcontext
from fractions import Fraction
from zoneinfo import ZoneInfo

LOCAL = ZoneInfo("Asia/Bangkok")
FUEL_VARIANCE_LIMIT = Decimal("15")


def estimate_fuel(
    distance_km: Decimal,
    idle_hours: Decimal,
    driving_l_per_100km: Decimal,
    idling_l_per_hour: Decimal,
) -> Decimal:
    values = (distance_km, idle_hours, driving_l_per_100km, idling_l_per_hour)
    if any(not value.is_finite() or value < 0 for value in values):
        raise ValueError("Fuel calculation requires finite nonnegative inputs")
    return decimal_value(
        _fuel_fraction(distance_km, Fraction(idle_hours), driving_l_per_100km, idling_l_per_hour)
    )


def _fuel_fraction(
    distance_km: Decimal, idle_hours: Fraction, driving: Decimal, idle: Decimal
) -> Fraction:
    return Fraction(distance_km) * Fraction(driving) / 100 + idle_hours * Fraction(idle)


def observed_fuel(
    distance_km: Decimal, idle_seconds: Decimal, driving: Decimal, idle: Decimal
) -> Fraction:
    values = (distance_km, idle_seconds, driving, idle)
    if any(not v.is_finite() or v < 0 for v in values):
        raise ValueError("Fuel calculation requires finite nonnegative observations")
    return _fuel_fraction(distance_km, Fraction(idle_seconds) / 3600, driving, idle)


def decimal_value(value: Fraction) -> Decimal:
    # Rendering only. Never feed a rounded repeating decimal into the alert gate.
    with localcontext() as context:
        context.prec = 40
        return Decimal(value.numerator) / Decimal(value.denominator)


def exact_variance(actual: Decimal, expected: Fraction) -> Fraction:
    if not actual.is_finite() or actual < 0 or expected <= 0:
        raise ValueError("A positive estimate is required to calculate fuel variance")
    return (Fraction(actual) - expected) * 100 / expected


def fuel_variance(actual: Decimal, estimated: Decimal) -> Decimal:
    # No business decision for missing/zero estimates is made by this calculation.
    if not actual.is_finite() or actual < 0 or not estimated.is_finite() or estimated <= 0:
        raise ValueError("A positive estimate is required to calculate fuel variance")
    return decimal_value(exact_variance(actual, Fraction(estimated)))


def fuel_alert(actual: Decimal, estimated: Decimal) -> bool:
    if not estimated.is_finite():
        raise ValueError("A positive estimate is required to calculate fuel variance")
    return abs(exact_variance(actual, Fraction(estimated))) > Fraction(FUEL_VARIANCE_LIMIT)


def outside_hours(at: datetime) -> bool:
    if at.tzinfo is None:
        raise ValueError("Event time requires a timezone")
    local = at.astimezone(LOCAL).time()
    return local >= time(18) or local < time(7, 30)


def safety_transition(old: str, new: str) -> bool:
    return (old, new) in {("NEW", "SEEN"), ("SEEN", "RESOLVED")}

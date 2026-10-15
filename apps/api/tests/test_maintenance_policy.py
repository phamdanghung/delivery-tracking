from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.maintenance_policy import maintenance_status

TODAY = date(2026, 10, 14)


def rule(**changes):
    return {
        "interval_km": 1000,
        "lead_km": 100,
        "interval_days": 30,
        "lead_days": 5,
        "baseline_odometer_km": Decimal("10000"),
        "baseline_date": TODAY,
        "baseline_source": "ADMIN",
        **changes,
    }


@pytest.mark.parametrize(
    "km,status", [(10899, "NOT_DUE"), (10900, "SOON"), (11000, "DUE"), (11001, "OVERDUE")]
)
def test_km_boundary_and_configured_lead(km, status):
    result = maintenance_status(rule(interval_days=None), None, Decimal(km), TODAY)
    assert result["status"] == status


@pytest.mark.parametrize(
    "days,status", [(24, "NOT_DUE"), (25, "SOON"), (30, "DUE"), (31, "OVERDUE")]
)
def test_calendar_boundary_and_configured_lead(days, status):
    assert (
        maintenance_status(rule(interval_km=None), None, None, TODAY + timedelta(days=days))[
            "status"
        ]
        == status
    )


def test_either_criterion_can_be_first_without_discarding_the_other():
    assert maintenance_status(rule(), None, Decimal(11000), TODAY)["status"] == "DUE"
    assert (
        maintenance_status(rule(), None, Decimal(10000), TODAY + timedelta(days=31))["status"]
        == "OVERDUE"
    )


def test_event_resets_entire_cycle_not_just_date():
    event = {
        "id": "service",
        "service_date": TODAY + timedelta(days=30),
        "odometer_km": Decimal(11000),
        "odometer_source": "ADMIN",
    }
    result = maintenance_status(rule(), event, Decimal(11000), TODAY + timedelta(days=30))
    assert result["status"] == "NOT_DUE"
    assert result["baseline_event_id"] == "service"
    event["odometer_km"] = None
    assert (
        maintenance_status(rule(), event, Decimal(11000), TODAY + timedelta(days=30))["status"]
        == "INSUFFICIENT"
    )


def test_missing_odometer_is_not_zero_and_known_due_date_is_still_reported():
    assert maintenance_status(rule(), None, None, TODAY)["status"] == "INSUFFICIENT"
    assert maintenance_status(rule(), None, None, TODAY + timedelta(days=30))["status"] == "DUE"


def test_lead_is_not_guessed_and_reading_must_not_precede_anchor():
    assert (
        "LEAD_KM_MISSING"
        in maintenance_status(rule(lead_km=None), None, Decimal(10500), TODAY)["reasons"]
    )
    assert (
        "ODOMETER_BEFORE_BASELINE"
        in maintenance_status(rule(), None, Decimal(9999), TODAY)["reasons"]
    )

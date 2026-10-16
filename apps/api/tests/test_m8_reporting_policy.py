from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.reporting_policy import attempt_evidence, attempt_totals


def history(kind="FIXED_TIME", seconds=0):
    appointment = datetime(2026, 10, 16, 3, tzinfo=UTC)
    arrival = appointment + timedelta(seconds=seconds)
    trip, delivery, stop, plan, actor = [uuid4() for _ in range(5)]
    row = dict(
        trip_id=trip,
        trip_date="2026-10-16",
        vehicle_id=uuid4(),
        delivery_id=delivery,
        delivery_code="REPORT-ATTEMPT",
        attempt_id=stop,
        attempt_status="DELIVERED",
        arrived_at=arrival,
        trip_created_at=appointment - timedelta(hours=2),
        completed_at=appointment + timedelta(hours=2),
    )
    original = dict(
        stop_id=str(stop),
        delivery_id=str(delivery),
        commitment_type=kind,
        appointment_at=appointment.isoformat(),
        window_start=(appointment - timedelta(minutes=15)).isoformat(),
        window_end=(appointment + timedelta(minutes=15)).isoformat(),
        deadline_at=appointment.isoformat(),
    )
    plans = [
        dict(
            id=plan,
            trip_id=trip,
            input_json=dict(
                source=dict(trip=dict(id=str(trip), trip_date=row["trip_date"]), stops=[original]),
                policy=dict(tolerance_s=900),
            ),
        )
    ]
    events = [
        dict(
            id=uuid4(),
            delivery_id=delivery,
            from_status="EN_ROUTE",
            to_status="ARRIVED",
            event_time=arrival,
            source="WEB",
            request_id="arrival",
        )
    ]
    audits = [
        dict(
            id=uuid4(),
            resource_id=str(delivery),
            action="STATUS",
            created_at=arrival,
            request_id="arrival",
            actor_user_id=actor,
            after_json=dict(delivery=dict(status="ARRIVED", trip_id=str(trip))),
        )
    ]
    return row, plans, events, audits


@pytest.mark.parametrize(
    "kind,seconds,status",
    [
        (kind, seconds, status)
        for kind in ("FIXED_TIME", "TIME_WINDOW")
        for seconds, status in [
            (-901, "EARLY"),
            (-900, "ON_TIME"),
            (0, "ON_TIME"),
            (900, "ON_TIME"),
            (901, "LATE"),
        ]
    ]
    + [
        ("BEFORE_DEADLINE", -3600, "ON_TIME"),
        ("BEFORE_DEADLINE", 0, "ON_TIME"),
        ("BEFORE_DEADLINE", 1, "LATE"),
    ],
)
def test_classification_uses_inclusive_boundaries_and_separates_early(kind, seconds, status):
    result = attempt_evidence(*history(kind, seconds))
    assert result["status"] == status
    assert result["arrival_event_id"]
    assert result["arrival_audit_id"]
    assert result["commitment"]["route_plan_id"]
    assert result["unknown_reasons"] == []


def corrected_history(rearrive=True):
    row, plans, events, audits = history()
    corrected = row["arrived_at"] + timedelta(seconds=10)
    event = dict(
        id=uuid4(),
        delivery_id=row["delivery_id"],
        from_status="ARRIVED",
        to_status="EN_ROUTE",
        event_time=corrected,
        request_id="correction",
    )
    audit = dict(
        id=uuid4(),
        resource_id=str(row["delivery_id"]),
        action="CORRECT_ARRIVED",
        created_at=corrected,
        request_id="correction",
        actor_user_id=uuid4(),
        reason="GPS sai",
        before_json=dict(trip_id=str(row["trip_id"]), status="ARRIVED"),
        after_json=dict(trip_id=str(row["trip_id"]), status="EN_ROUTE"),
    )
    events.append(event)
    audits.append(audit)
    if rearrive:
        arrival = corrected + timedelta(seconds=10)
        new_event, new_audit = deepcopy(events[0]), deepcopy(audits[0])
        new_event.update(id=uuid4(), event_time=arrival, request_id="rearrival")
        new_audit.update(id=uuid4(), created_at=arrival, request_id="rearrival")
        events.append(new_event)
        audits.append(new_audit)
        row["arrived_at"] = arrival
    return row, plans, events, audits


def test_corrected_arrival_is_not_used_and_final_valid_arrival_is_traceable():
    result = attempt_evidence(*corrected_history())
    assert result["status"] == "ON_TIME"
    assert len(result["corrections"]) == 1
    result = attempt_evidence(*corrected_history(False))
    assert result["status"] == "UNKNOWN"
    assert result["unknown_reasons"] == ["ARRIVAL_WAS_CORRECTED"]
    assert len(result["corrections"]) == 1


def test_missing_current_arrival_retains_correction_trace():
    evidence = corrected_history(False)
    evidence[0]["arrived_at"] = None
    result = attempt_evidence(*evidence)
    assert result["status"] == "UNKNOWN"
    assert len(result["corrections"]) == 1


@pytest.mark.parametrize("missing", ["event", "audit"])
def test_incomplete_correction_history_is_unknown_in_both_directions(missing):
    evidence = corrected_history()
    evidence[2 if missing == "event" else 3].pop(1)
    assert attempt_evidence(*evidence)["unknown_reasons"] == ["CORRECTION_HISTORY_INCOMPLETE"]


@pytest.mark.parametrize("missing", ["plan", "event", "audit", "date", "source", "tolerance"])
def test_missing_evidence_is_unknown_without_current_record_fallback(missing):
    row, plans, events, audits = history()
    if missing == "plan":
        plans.clear()
    elif missing == "event":
        events.clear()
    elif missing == "audit":
        audits.clear()
    elif missing == "date":
        row["trip_date"] = "invalid"
    elif missing == "source":
        plans[0]["input_json"]["source"] = []
    else:
        plans[0]["input_json"]["policy"].clear()
    result = attempt_evidence(row, plans, events, audits)
    assert result["status"] == "UNKNOWN"
    assert result["unknown_reasons"]


def test_approved_snapshot_tolerance_is_used_instead_of_current_settings():
    row, plans, events, audits = history(seconds=901)
    plans[0]["input_json"]["policy"]["tolerance_s"] = 1200
    assert attempt_evidence(row, plans, events, audits)["status"] == "ON_TIME"


def test_unknown_excluded_from_three_group_denominator_and_empty_rates_are_null():
    items = [
        dict(status=s, attempt_status="FAILED") for s in ["EARLY", "ON_TIME", "LATE", "UNKNOWN"]
    ]
    counts = attempt_totals(items)
    assert counts["eligible_attempts"] == 3
    assert counts["unknown"] == 1
    assert counts["failed_attempts"] == 4
    assert counts["on_time_rate"] == counts["early_rate"] == counts["late_rate"] == Decimal(1) / 3
    assert attempt_totals([])["on_time_rate"] is None

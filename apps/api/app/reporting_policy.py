"""Read historical attempt evidence; never substitute current delivery commitments."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any


def aware(value: Any) -> datetime | None:
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        return parsed.astimezone(UTC) if parsed.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def attempt_evidence(
    row: dict[str, Any],
    plans: list[dict[str, Any]],
    events: list[dict[str, Any]],
    audits: list[dict[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "trip_id": row["trip_id"],
        "trip_date": row.get("trip_date"),
        "vehicle_id": row.get("vehicle_id"),
        "delivery_id": row["delivery_id"],
        "delivery_code": row["delivery_code"],
        "attempt_id": row["attempt_id"],
        "attempt_status": row["attempt_status"],
        "status": "UNKNOWN",
        "unknown_reasons": [],
        "commitment": None,
        "arrival_event_id": None,
        "arrival_audit_id": None,
        "arrived_at": None,
        "corrections": [],
    }

    def unknown(reason: str) -> dict[str, Any]:
        result["unknown_reasons"].append(reason)
        return result

    try:
        date.fromisoformat(str(row.get("trip_date")))
    except ValueError:
        return unknown("TRIP_DATE_MISSING")
    selected = [p for p in plans if str(p["trip_id"]) == str(row["trip_id"])]
    if len(selected) != 1:
        return unknown("APPROVED_COMMITMENT_MISSING_OR_AMBIGUOUS")
    plan = selected[0]
    snapshot = plan.get("input_json", {})
    source = snapshot.get("source", {}) if isinstance(snapshot, dict) else {}
    if not isinstance(source, dict):
        return unknown("COMMITMENT_TRIP_HISTORY_INCOMPLETE")
    trip = source.get("trip", {})
    stops = source.get("stops", [])
    if (
        not isinstance(trip, dict)
        or not isinstance(stops, list)
        or str(trip.get("id")) != str(row["trip_id"])
        or str(trip.get("trip_date")) != str(row["trip_date"])
    ):
        return unknown("COMMITMENT_TRIP_HISTORY_INCOMPLETE")
    commitments = [
        s
        for s in stops
        if isinstance(s, dict)
        and str(s.get("stop_id")) == str(row["attempt_id"])
        and str(s.get("delivery_id")) == str(row["delivery_id"])
    ]
    if len(commitments) != 1:
        return unknown("ATTEMPT_COMMITMENT_MISSING_OR_AMBIGUOUS")
    original = commitments[0]
    kind = original.get("commitment_type")
    appointment = aware(original.get("appointment_at"))
    lower, upper, tolerance = None, None, None
    if kind == "FIXED_TIME":
        policy = snapshot.get("policy", {})
        tolerance = policy.get("tolerance_s") if isinstance(policy, dict) else None
        if appointment is None or type(tolerance) is not int or tolerance < 0:
            return unknown("FIXED_TIME_HISTORY_INCOMPLETE")
        try:
            lower, upper = (
                appointment - timedelta(seconds=tolerance),
                appointment + timedelta(seconds=tolerance),
            )
        except OverflowError:
            return unknown("FIXED_TIME_HISTORY_INCOMPLETE")
    elif kind == "TIME_WINDOW":
        lower, upper = aware(original.get("window_start")), aware(original.get("window_end"))
        if lower is None or upper is None or lower > upper:
            return unknown("TIME_WINDOW_HISTORY_INCOMPLETE")
    elif kind == "BEFORE_DEADLINE":
        upper = aware(original.get("deadline_at"))
        if upper is None:
            return unknown("DEADLINE_HISTORY_INCOMPLETE")
    else:
        return unknown("COMMITMENT_TYPE_MISSING")
    result["commitment"] = {
        "route_plan_id": plan["id"],
        "type": kind,
        "appointment_at": appointment,
        "window_start": aware(original.get("window_start")),
        "window_end": aware(original.get("window_end")),
        "deadline_at": aware(original.get("deadline_at")),
        "tolerance_seconds": tolerance,
        "valid_from": lower,
        "valid_to": upper,
    }
    arrived = aware(row.get("arrived_at"))
    started = aware(row.get("trip_created_at"))
    ends = [
        v
        for name in ("completed_at", "next_attempt_created_at")
        if (v := aware(row.get(name))) is not None
    ]
    ended = min(ends) if ends else None
    if started is None or row.get("ambiguous_attempt_history"):
        return unknown("ATTEMPT_HISTORY_INCOMPLETE")
    own_events = [e for e in events if str(e["delivery_id"]) == str(row["delivery_id"])]
    own_audits = [a for a in audits if str(a["resource_id"]) == str(row["delivery_id"])]
    corrections = []
    for event in own_events:
        at = aware(event["event_time"])
        if (
            event["from_status"] != "ARRIVED"
            or event["to_status"] != "EN_ROUTE"
            or at is None
            or at < started
            or (ended is not None and at > ended)
        ):
            continue
        references = []
        for entry in own_audits:
            before, after = entry.get("before_json") or {}, entry.get("after_json") or {}
            if (
                entry["action"] == "CORRECT_ARRIVED"
                and event.get("request_id")
                and entry.get("request_id") == event["request_id"]
                and isinstance(before, dict)
                and isinstance(after, dict)
                and str(before.get("trip_id")) == str(row["trip_id"])
                and str(after.get("trip_id")) == str(row["trip_id"])
                and before.get("status") == "ARRIVED"
                and after.get("status") == "EN_ROUTE"
                and entry.get("reason")
                and entry.get("actor_user_id")
            ):
                references.append(entry)
        if len(references) != 1:
            return unknown("CORRECTION_HISTORY_INCOMPLETE")
        entry = references[0]
        corrections.append(
            {
                "event_id": event["id"],
                "audit_id": entry["id"],
                "at": at,
                "actor_user_id": entry["actor_user_id"],
                "reason": entry["reason"],
            }
        )

    result["corrections"] = corrections
    # Audit and status-event histories must agree in both directions.
    own_correction_audits = [
        a
        for a in own_audits
        if a["action"] == "CORRECT_ARRIVED"
        and isinstance(a.get("after_json"), dict)
        and str(a["after_json"].get("trip_id")) == str(row["trip_id"])
    ]
    if {str(a["id"]) for a in own_correction_audits} != {str(c["audit_id"]) for c in corrections}:
        return unknown("CORRECTION_HISTORY_INCOMPLETE")
    if arrived is None:
        return unknown("VALID_ARRIVAL_MISSING")
    if any(c["at"] >= arrived for c in corrections):
        return unknown("ARRIVAL_WAS_CORRECTED")
    arrivals = [
        e for e in own_events if e["to_status"] == "ARRIVED" and aware(e["event_time"]) == arrived
    ]
    if len(arrivals) != 1:
        return unknown("ARRIVAL_EVENT_MISSING_OR_AMBIGUOUS")
    arrival = arrivals[0]
    associated = []
    for entry in own_audits:
        if not arrival.get("request_id") or entry.get("request_id") != arrival["request_id"]:
            continue
        at = aware(entry["created_at"])
        if at is None or at < started or (ended is not None and at > ended):
            continue
        after = entry.get("after_json") or {}
        if not isinstance(after, dict):
            continue
        if entry["action"] == "AUTO_ARRIVED" and arrival["source"] == "GEOFENCE":
            if after.get("status") == "ARRIVED" and aware(after.get("gps_at")) == arrived:
                associated.append(entry)
        elif entry["action"] == "STATUS":
            delivery = after.get("delivery", {})
            if (
                isinstance(delivery, dict)
                and delivery.get("status") == "ARRIVED"
                and str(delivery.get("trip_id")) == str(row["trip_id"])
            ):
                associated.append(entry)
    if len(associated) != 1:
        return unknown("ARRIVAL_AUDIT_MISSING_OR_AMBIGUOUS")
    result["status"] = (
        "EARLY"
        if lower is not None and arrived < lower
        else "LATE"
        if arrived > upper
        else "ON_TIME"
    )
    result.update(
        arrived_at=arrived,
        arrival_event_id=arrival["id"],
        arrival_audit_id=associated[0]["id"],
        corrections=corrections,
    )
    return result


def attempt_totals(items: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        kind: sum(r["status"] == kind for r in items)
        for kind in ("EARLY", "ON_TIME", "LATE", "UNKNOWN")
    }
    eligible = sum(counts[k] for k in ("EARLY", "ON_TIME", "LATE"))
    return {
        "attempts": len(items),
        "failed_attempts": sum(r["attempt_status"] == "FAILED" for r in items),
        "eligible_attempts": eligible,
        **{k.lower(): v for k, v in counts.items()},
        **{
            k.lower() + "_rate": Decimal(counts[k]) / eligible if eligible else None
            for k in ("EARLY", "ON_TIME", "LATE")
        },
    }

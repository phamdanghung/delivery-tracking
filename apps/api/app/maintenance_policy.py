"""Per-vehicle maintenance without invented baselines or lead thresholds (DEC-049)."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any


def maintenance_status(
    rule: dict[str, Any],
    latest_event: dict[str, Any] | None,
    odometer_km: Decimal | None,
    today: date,
) -> dict[str, Any]:
    # A later maintenance event resets the entire cycle. Do not reuse a historic
    # odometer anchor when the latest service has no trustworthy reading.
    baseline_date = latest_event["service_date"] if latest_event else rule.get("baseline_date")
    baseline_km = (
        latest_event.get("odometer_km") if latest_event else rule.get("baseline_odometer_km")
    )
    missing: list[str] = []
    criteria: list[dict[str, Any]] = []
    if rule.get("interval_km") is not None:
        if baseline_km is None or odometer_km is None:
            missing.append("ODOMETER_MISSING")
        elif odometer_km < baseline_km:
            missing.append("ODOMETER_BEFORE_BASELINE")
        elif rule.get("lead_km") is None:
            missing.append("LEAD_KM_MISSING")
        else:
            due_km = baseline_km + rule["interval_km"]
            remaining = due_km - odometer_km
            state = (
                "OVERDUE"
                if remaining < 0
                else "DUE"
                if remaining == 0
                else "SOON"
                if remaining <= rule["lead_km"]
                else "NOT_DUE"
            )
            criteria.append(
                {"criterion": "KM", "status": state, "due_km": due_km, "remaining_km": remaining}
            )
    if rule.get("interval_days") is not None:
        if baseline_date is None:
            missing.append("BASELINE_DATE_MISSING")
        elif rule.get("lead_days") is None:
            missing.append("LEAD_DAYS_MISSING")
        elif baseline_date > today:
            missing.append("BASELINE_DATE_IN_FUTURE")
        else:
            due_date = baseline_date + timedelta(days=rule["interval_days"])
            remaining_days = (due_date - today).days
            state = (
                "OVERDUE"
                if remaining_days < 0
                else "DUE"
                if remaining_days == 0
                else "SOON"
                if remaining_days <= rule["lead_days"]
                else "NOT_DUE"
            )
            criteria.append(
                {
                    "criterion": "DAYS",
                    "status": state,
                    "due_date": due_date,
                    "remaining_days": remaining_days,
                }
            )
    if not rule.get("interval_km") and not rule.get("interval_days"):
        missing.append("INTERVAL_MISSING")
    ranks = {"NOT_DUE": 0, "SOON": 1, "DUE": 2, "OVERDUE": 3}
    state = max((c["status"] for c in criteria), key=lambda s: ranks[s], default="INSUFFICIENT")
    # A known due criterion remains due even if another lacks data. Otherwise
    # lack of data must not produce a false 'not due' or 'soon' assurance.
    if missing and state not in ("DUE", "OVERDUE"):
        state = "INSUFFICIENT"
    return {
        "status": state,
        "reasons": missing,
        "criteria": criteria,
        "baseline_event_id": latest_event.get("id") if latest_event else None,
        "baseline_source": latest_event.get("odometer_source")
        if latest_event
        else rule.get("baseline_source"),
    }

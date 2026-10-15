"""Traccar observations only. No route distance or spatial fallback (DEC-047)."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException

from app.gps import normalize, timestamp
from app.traccar import Traccar


def observed_segment(
    positions: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    device: int,
    start: datetime,
    end: datetime,
    require_idle: bool,
) -> dict[str, Any]:
    reasons: list[str] = []
    points = sorted(
        [
            normalize(
                {
                    **p,
                    "attributes": p.get("attributes")
                    if isinstance(p.get("attributes"), dict)
                    else {},
                }
            )
            for p in positions
            if p.get("deviceId") == device
        ],
        key=lambda p: p["gps_at"] or start,
    )
    if len(points) < 2:
        return {"reasons": ["GPS_NO_COVERAGE"], "distance_km": None, "idle_hours": None}
    if any(not p["valid"] or not start <= p["gps_at"] <= end for p in points):
        reasons.append("GPS_INVALID")
    # DEC-015/M1 considers gaps over 120 seconds LOST; never bridge such gaps.
    if (
        points[0]["gps_at"] is None
        or points[-1]["gps_at"] is None
        or (points[0]["gps_at"] - start).total_seconds() > 120
        or (end - points[-1]["gps_at"]).total_seconds() > 120
    ):
        reasons.append("GPS_BOUNDARY_GAP")
    idle_seconds = Decimal("0")
    idle_unknown = any(p["engine_state"] == "UNKNOWN" for p in points)
    for previous, current in zip(points, points[1:], strict=False):
        if previous["gps_at"] is None or current["gps_at"] is None:
            continue
        duration = current["gps_at"] - previous["gps_at"]
        seconds = (
            Decimal(duration.days * 86400 + duration.seconds)
            + Decimal(duration.microseconds) / 1000000
        )
        if seconds <= 0 or seconds > 120:
            reasons.append("GPS_GAP")
            continue
        if require_idle and (
            previous["engine_state"] == "UNKNOWN" or current["engine_state"] == "UNKNOWN"
        ):
            reasons.append("ACC_INSUFFICIENT")
        if previous["engine_state"] == "IDLING" and current["engine_state"] != "UNKNOWN":
            # M1 convention: sampled transitions start at the fix timestamp.
            # Uncovered boundaries are never extrapolated.
            idle_seconds += seconds
    rows = [s for s in summaries if s.get("deviceId") == device]
    distance: Decimal | None = None
    if len(rows) != 1:
        reasons.append("DISTANCE_NO_REPORT")
    else:
        row = rows[0]
        first, last = timestamp(row.get("startTime")), timestamp(row.get("endTime"))
        try:
            meters = Decimal(str(row["distance"]))
            if not meters.is_finite() or meters < 0:
                raise ValueError("Invalid distance")
            distance = meters / 1000
        except (KeyError, InvalidOperation, ValueError):
            reasons.append("DISTANCE_INVALID")
        if first != points[0]["gps_at"] or last != points[-1]["gps_at"]:
            reasons.append("DISTANCE_COVERAGE_MISMATCH")
    return {
        "distance_km": distance,
        "idle_hours": None if idle_unknown else idle_seconds / 3600,
        "idle_seconds": None if idle_unknown else idle_seconds,
        "idle_required": require_idle,
        "idle_status": "INSUFFICIENT" if idle_unknown else "COMPLETE",
        "reasons": sorted(set(reasons)),
        "position_ids": [p["position_id"] for p in points],
        "source": "TRACCAR",
        "observed_from": points[0]["gps_at"],
        "observed_to": points[-1]["gps_at"],
    }


def telemetry(device: int | None, start: datetime, end: datetime, idle: bool) -> dict[str, Any]:
    if device is None:
        return {"reasons": ["VEHICLE_UNMAPPED"], "distance_km": None, "idle_hours": None}
    params = {"deviceId": device, "from": start.isoformat(), "to": end.isoformat()}
    provider = Traccar()
    try:
        positions = provider.get("positions", params)
        summaries = provider.get("reports/summary", params)
    except HTTPException:
        return {"reasons": ["TRACCAR_UNAVAILABLE"], "distance_km": None, "idle_hours": None}
    return observed_segment(positions, summaries, device, start, end, idle)

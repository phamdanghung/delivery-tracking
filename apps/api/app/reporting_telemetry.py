"""Verified historical telemetry intervals, with no extrapolation across missing fixes."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException

from app.fuel_telemetry import observed_segment
from app.gps import normalize
from app.traccar import Traccar


def intervals(
    positions: list[dict[str, Any]], device: int, start: datetime, end: datetime
) -> list[dict[str, Any]]:
    points = []
    seen: dict[int, dict[str, Any]] = {}
    for raw in positions:
        if raw.get("deviceId") != device:
            continue
        identifier = raw.get("id")
        if type(identifier) is not int:
            continue
        if identifier in seen:
            if seen[identifier] != raw:
                # Contradictory copies are not trustworthy observations.
                return []
            continue
        seen[identifier] = raw
        safe = {
            **raw,
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
        }
        item = normalize(safe)
        if item["gps_at"] is None:
            # Cannot order this observation; do not bridge an unknown interval.
            return []
        if start <= item["gps_at"] <= end:
            points.append((item, safe))
    points.sort(key=lambda p: p[0]["gps_at"])
    result = []
    for (before, raw_before), (after, raw_after) in zip(points, points[1:], strict=False):
        seconds = Decimal(str((after["gps_at"] - before["gps_at"]).total_seconds()))
        if not before["valid"] or not after["valid"] or not 0 < seconds <= 120:
            continue
        state = before["engine_state"] if after["engine_state"] != "UNKNOWN" else "UNKNOWN"
        result.append(
            dict(
                from_at=before["gps_at"],
                to_at=after["gps_at"],
                seconds=seconds,
                engine_state=state,
                position_ids=[before["position_id"], after["position_id"]],
                raw_points=[raw_before, raw_after],
            )
        )
    return result


def observed_report(
    provider: Traccar, device: int | None, start: datetime, end: datetime
) -> dict[str, Any]:
    duration = Decimal(str((end - start).total_seconds()))
    result: dict[str, Any] = dict(
        operating_hours=None,
        moving_hours=None,
        idle_hours=None,
        distance_km=None,
        hours_quality="UNKNOWN",
        distance_quality="UNKNOWN",
        hours_coverage_seconds=Decimal(0),
        distance_coverage_seconds=Decimal(0),
        period_seconds=duration,
        reasons=[],
        intervals=[],
        source="TRACCAR",
        traccar_device_id=device,
    )
    if device is None:
        result["reasons"] = ["VEHICLE_UNMAPPED_OR_MAPPING_HISTORY_INCOMPLETE"]
        return result
    params = dict(deviceId=device, **{"from": start.isoformat(), "to": end.isoformat()})
    try:
        observations = provider.get("positions", params)
    except HTTPException:
        result["reasons"] = ["TRACCAR_UNAVAILABLE"]
        return result
    verified = intervals(observations, device, start, end)
    hours = [p for p in verified if p["engine_state"] != "UNKNOWN"]
    coverage = sum((p["seconds"] for p in hours), Decimal(0))
    result["hours_coverage_seconds"] = coverage
    if hours:
        moving = sum((p["seconds"] for p in hours if p["engine_state"] == "MOVING"), Decimal(0))
        idle = sum((p["seconds"] for p in hours if p["engine_state"] == "IDLING"), Decimal(0))
        result.update(
            moving_hours=moving / 3600,
            idle_hours=idle / 3600,
            operating_hours=(moving + idle) / 3600,
            hours_quality="VALID" if coverage == duration else "PARTIAL",
        )
    # Ask Traccar for each continuous verified span. Never count distance across gaps.
    groups: list[list[dict[str, Any]]] = []
    for item in verified:
        if groups and groups[-1][-1]["to_at"] == item["from_at"]:
            groups[-1].append(item)
        else:
            groups.append([item])
    distance, distance_coverage = Decimal(0), Decimal(0)
    for group in groups:
        first, last = group[0]["from_at"], group[-1]["to_at"]
        raw = [group[0]["raw_points"][0], *[p["raw_points"][1] for p in group]]
        try:
            summaries = provider.get(
                "reports/summary",
                dict(deviceId=device, **{"from": first.isoformat(), "to": last.isoformat()}),
            )
            segment = observed_segment(raw, summaries, device, first, last, False)
        except HTTPException:
            result["reasons"].append("TRACCAR_DISTANCE_UNAVAILABLE")
            continue
        if segment["reasons"] or segment["distance_km"] is None:
            result["reasons"].extend(segment["reasons"])
            continue
        distance += segment["distance_km"]
        distance_coverage += Decimal(str((last - first).total_seconds()))
        for item in group:
            item["distance_verified"] = True
    if distance_coverage:
        result.update(
            distance_km=distance,
            distance_coverage_seconds=distance_coverage,
            distance_quality="VALID" if distance_coverage == duration else "PARTIAL",
        )
    if coverage < duration:
        result["reasons"].append("HOURS_INCOMPLETE_COVERAGE")
    if distance_coverage < duration:
        result["reasons"].append("DISTANCE_INCOMPLETE_COVERAGE")
    result["reasons"] = sorted(set(result["reasons"]))
    result["intervals"] = [
        {k: v for k, v in p.items() if k != "raw_points"}
        | {"distance_verified": p.get("distance_verified", False)}
        for p in verified
    ]
    return result


def mapped_report(
    provider: Traccar, history: list[dict[str, Any]], start: datetime, end: datetime
) -> dict[str, Any]:
    """Do not attribute old-device telemetry using today's vehicle mapping."""
    result = observed_report(provider, None, start, end)
    result.update(mapping_audit_ids=[], traccar_device_ids=[])
    rows = sorted(history, key=lambda r: r["created_at"])
    segments: list[dict[str, Any]] = []
    for index, entry in enumerate(rows):
        lower = max(start, entry["created_at"])
        upper = min(end, rows[index + 1]["created_at"] if index + 1 < len(rows) else end)
        payload = entry.get("after_json")
        # Conflicting audit timestamps do not establish a unique mapping.
        tied = sum(r["created_at"] == entry["created_at"] for r in rows) > 1
        if lower >= upper or tied or not isinstance(payload, dict):
            continue
        device = payload.get("traccar_device_id")
        if type(device) is not int or device <= 0:
            continue
        if segments and segments[-1]["end"] == lower and segments[-1]["device"] == device:
            segments[-1]["end"] = upper
            segments[-1]["audits"].append(entry["id"])
        else:
            segments.append(dict(start=lower, end=upper, device=device, audits=[entry["id"]]))
    results = []
    for span in segments:
        observed = observed_report(provider, span["device"], span["start"], span["end"])
        result["mapping_audit_ids"].extend(span["audits"])
        result["traccar_device_ids"].append(span["device"])
        result["intervals"].extend(
            [
                {**p, "traccar_device_id": span["device"], "mapping_audit_ids": span["audits"]}
                for p in observed["intervals"]
            ]
        )
        results.append(observed)
    result["traccar_device_ids"] = sorted(set(result["traccar_device_ids"]))
    if len(result["traccar_device_ids"]) == 1:
        result["traccar_device_id"] = result["traccar_device_ids"][0]
    for name, coverage, fields in [
        (
            "hours_quality",
            "hours_coverage_seconds",
            ["moving_hours", "idle_hours", "operating_hours"],
        ),
        ("distance_quality", "distance_coverage_seconds", ["distance_km"]),
    ]:
        known = [r for r in results if r[name] != "UNKNOWN"]
        result[coverage] = sum((r[coverage] for r in known), Decimal(0))
        if known:
            for field in fields:
                result[field] = sum((r[field] for r in known), Decimal(0))
            result[name] = "VALID" if result[coverage] == result["period_seconds"] else "PARTIAL"
    result["reasons"] = sorted(set(reason for r in results for reason in r["reasons"]))
    if (
        sum((Decimal(str((s["end"] - s["start"]).total_seconds())) for s in segments), Decimal(0))
        < result["period_seconds"]
    ):
        result["reasons"].append("MAPPING_HISTORY_INCOMPLETE")
    return result

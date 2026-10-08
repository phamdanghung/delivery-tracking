import asyncio
import logging
import math
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from app.auth import Db, Operator
from app.config import get_settings
from app.database import engine_for, table
from app.schemas import GpsHistory, LivePosition, OdometerReport
from app.traccar import Traccar

router = APIRouter(prefix="/api/v1", tags=["gps"])
logger = logging.getLogger("fleet")


def freshness(gps_at: datetime | None, received_at: datetime | None, now: datetime) -> str:
    if gps_at is None or received_at is None or gps_at > now or received_at > now:
        return "LOST"
    age = max((now - gps_at).total_seconds(), (now - received_at).total_seconds())
    return "NORMAL" if age <= 30 else "STALE" if age <= 120 else "LOST"


def engine_state(speed: float | None, acc: bool | None, valid: bool = True) -> str:
    if not valid or speed is None or not math.isfinite(speed) or speed < 0 or acc is None:
        return "UNKNOWN"
    if acc is True:
        return "MOVING" if speed > 0 else "IDLING"
    return "PARKED" if speed == 0 else "UNKNOWN"


def timestamp(value: Any) -> datetime | None:
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.astimezone(UTC) if result.tzinfo else None
    except (ValueError, TypeError):
        return None


def acc_value(value: Any) -> bool | None:
    if value is True or value in ("true", "1", 1):
        return True
    if value is False or value in ("false", "0", 0):
        return False
    return None


def normalize(position: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    fix, received = timestamp(position.get("fixTime")), timestamp(position.get("serverTime"))
    try:
        lat, lon = float(position["latitude"]), float(position["longitude"])
        speed, course = float(position["speed"]) * 1.852, float(position["course"])
        valid = (
            position.get("valid") is True
            and all(math.isfinite(n) for n in (lat, lon, speed, course))
            and -90 <= lat <= 90
            and -180 <= lon <= 180
            and speed >= 0
            and 0 <= course <= 360
            and fix is not None
            and received is not None
            and fix <= now
            and received <= now
        )
    except (ValueError, TypeError, KeyError):
        lat, lon, speed, course, valid = 0.0, 0.0, 0.0, 0.0, False
    acc = acc_value(position.get("attributes", {}).get("ignition"))
    return {
        "position_id": position.get("id"),
        "traccar_device_id": position.get("deviceId"),
        "latitude": lat if valid else None,
        "longitude": lon if valid else None,
        "speed_kmh": speed if valid else None,
        "course": course if valid else None,
        "gps_at": fix,
        "server_received_at": received,
        "backend_received_at": now,
        "acc": acc,
        "engine_state": engine_state(speed, acc, valid),
        "valid": valid,
        "freshness": freshness(fix, received, now) if valid else "LOST",
        "position_label": "Vị trí hiện tại"
        if valid and freshness(fix, received, now) == "NORMAL"
        else "Vị trí cuối ghi nhận"
        if valid
        else "GPS không hợp lệ",
    }


def ingest(db: Connection, raw: dict[str, Any]) -> bool:
    item = normalize(raw)
    if not item["valid"] or not isinstance(item["position_id"], int):
        return False
    db.execute(text("SELECT pg_advisory_xact_lock(73210402)"))
    vehicles, snapshots, events = (
        table("vehicles", db),
        table("gps_snapshots", db),
        table("vehicle_state_events", db),
    )
    vehicle = db.execute(
        select(vehicles.c.id)
        .where(vehicles.c.traccar_device_id == item["traccar_device_id"])
        .with_for_update()
    ).first()
    if vehicle is None:
        return False
    vehicle_id = vehicle[0]
    old = (
        db.execute(select(snapshots).where(snapshots.c.vehicle_id == vehicle_id)).mappings().first()
    )
    if old and (old["gps_at"] > item["gps_at"] or old["position_id"] == item["position_id"]):
        return False
    state = db.execute(
        select(events).where(events.c.vehicle_id == vehicle_id, events.c.ended_at.is_(None))
    )
    current = state.mappings().first()
    gap = old is not None and (item["gps_at"] - old["gps_at"]).total_seconds() > 120
    if current and (current["engine_state"] != item["engine_state"] or gap):
        end = old["gps_at"] if gap and old else item["gps_at"]
        db.execute(
            events.update()
            .where(events.c.id == current["id"])
            .values(ended_at=max(end, current["started_at"]))
        )
        current = None
    if current is None:
        db.execute(
            events.insert().values(
                vehicle_id=vehicle_id, engine_state=item["engine_state"], started_at=item["gps_at"]
            )
        )
    values = {
        key: item[key]
        for key in (
            "traccar_device_id",
            "position_id",
            "latitude",
            "longitude",
            "speed_kmh",
            "course",
            "gps_at",
            "server_received_at",
            "backend_received_at",
            "acc",
            "engine_state",
        )
    }
    statement = insert(snapshots).values(vehicle_id=vehicle_id, **values)
    db.execute(
        statement.on_conflict_do_update(index_elements=[snapshots.c.vehicle_id], set_=values)
    )
    from app.geofence import process_position

    process_position(db, vehicle_id, item)
    return True


def ingest_many(positions: list[dict[str, Any]]) -> None:
    engine = engine_for(get_settings().database_url.get_secret_value())
    with engine.begin() as db:
        for position in positions:
            ingest(db, position)


def find_vehicle(db: Connection, vehicle_id: UUID) -> dict[str, Any]:
    vehicles = table("vehicles", db)
    row = db.execute(select(vehicles).where(vehicles.c.id == vehicle_id)).mappings().first()
    if row is None:
        raise HTTPException(404, "Không tìm thấy xe")
    return dict(row)


@router.get("/vehicles/{vehicle_id}/live", response_model=LivePosition)
def live(vehicle_id: UUID, user: Operator, db: Db) -> dict[str, Any]:
    vehicle = find_vehicle(db, vehicle_id)
    device = vehicle["traccar_device_id"]
    if device is None:
        return {
            "vehicle_id": vehicle_id,
            "position": None,
            "freshness": "LOST",
            "reason": "UNMAPPED",
        }
    positions = Traccar().get("positions", {"deviceId": device})
    positions = [item for item in positions if item.get("deviceId") == device]
    if not positions:
        return {
            "vehicle_id": vehicle_id,
            "position": None,
            "freshness": "LOST",
            "reason": "NO_DATA",
        }
    raw = max(
        positions, key=lambda p: timestamp(p.get("fixTime")) or datetime.min.replace(tzinfo=UTC)
    )
    ingest(db, raw)
    result = normalize(raw)
    return {
        "vehicle_id": vehicle_id,
        "position": result,
        "freshness": result["freshness"],
        "reason": None,
    }


def history_data(positions: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    points = sorted(
        [normalize(p, now) for p in positions],
        key=lambda p: p["gps_at"] or datetime.min.replace(tzinfo=UTC),
    )
    segments: list[list[dict[str, Any]]] = []
    gaps: list[dict[str, Any]] = []
    stops: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    stop: dict[str, Any] | None = None
    for point in points:
        invalid = not point["valid"]
        gap = previous is not None and (
            invalid
            or not previous["valid"]
            or (point["gps_at"] - previous["gps_at"]).total_seconds() > 120
        )
        if gap:
            gaps.append(
                {
                    "from": previous["gps_at"] if previous else None,
                    "to": point["gps_at"],
                    "reason": "MISSING_OR_INVALID_GPS",
                }
            )
        if invalid or gap or point["engine_state"] not in ("IDLING", "PARKED"):
            if stop:
                stops.append(stop)
                stop = None
        if not invalid:
            if previous is None or gap or not segments:
                segments.append([])
            segments[-1].append(point)
            if point["engine_state"] in ("IDLING", "PARKED"):
                if stop and stop["engine_state"] != point["engine_state"]:
                    stops.append(stop)
                    stop = None
                if stop is None:
                    stop = {
                        "started_at": point["gps_at"],
                        "ended_at": point["gps_at"],
                        "duration_seconds": 0.0,
                        "engine_state": point["engine_state"],
                        "latitude": point["latitude"],
                        "longitude": point["longitude"],
                    }
                stop["ended_at"] = point["gps_at"]
                stop["duration_seconds"] = (point["gps_at"] - stop["started_at"]).total_seconds()
        previous = point
    if stop:
        stops.append(stop)
    return {"segments": segments, "stops": stops, "gaps": gaps, "points": points}


def interval(start: datetime, end: datetime) -> None:
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise HTTPException(422, "Khoảng thời gian cần timezone và bắt đầu trước kết thúc")
    if (end - start).total_seconds() > 31 * 86400:
        raise HTTPException(422, "Mỗi truy vấn tối đa 31 ngày; hãy chia khoảng thời gian")


@router.get("/vehicles/{vehicle_id}/history", response_model=GpsHistory)
def history(
    vehicle_id: UUID,
    user: Operator,
    db: Db,
    start: Annotated[datetime, Query(alias="from")],
    end: Annotated[datetime, Query(alias="to")],
) -> dict[str, Any]:
    interval(start, end)
    device = find_vehicle(db, vehicle_id)["traccar_device_id"]
    if device is None:
        return {"segments": [], "stops": [], "gaps": [], "points": []}
    positions = Traccar().get(
        "positions", {"deviceId": device, "from": start.isoformat(), "to": end.isoformat()}
    )
    return history_data([p for p in positions if p.get("deviceId") == device])


@router.get(
    "/vehicles/{vehicle_id}/odometer",
    response_model=OdometerReport,
    response_model_exclude_unset=True,
)
def odometer(
    vehicle_id: UUID,
    user: Operator,
    db: Db,
    start: Annotated[datetime, Query(alias="from")],
    end: Annotated[datetime, Query(alias="to")],
) -> dict[str, Any]:
    interval(start, end)
    device = find_vehicle(db, vehicle_id)["traccar_device_id"]
    if device is None:
        return {"distance_km": None, "source": "TRACCAR", "reason": "UNMAPPED"}
    reports = Traccar().get(
        "reports/summary", {"deviceId": device, "from": start.isoformat(), "to": end.isoformat()}
    )
    distance = sum(
        float(report.get("distance", 0)) for report in reports if report.get("deviceId") == device
    )
    return {
        "distance_km": distance / 1000,
        "source": "TRACCAR_REPORT_SUMMARY",
        "from": start,
        "to": end,
        "reason": None,
    }


async def poll_worker() -> None:
    while True:
        try:
            positions = await asyncio.to_thread(Traccar().get, "positions")
            await asyncio.to_thread(ingest_many, positions)
        except Exception:
            logger.warning("gps_rest_unavailable", extra={"dependency": "traccar"})
        await asyncio.sleep(get_settings().gps_poll_seconds)


async def socket_worker() -> None:
    while True:
        try:
            async for position in Traccar().positions():
                await asyncio.to_thread(ingest_many, [position])
        except Exception:
            logger.warning("gps_socket_unavailable", extra={"dependency": "traccar"})
        await asyncio.sleep(5)

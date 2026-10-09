"""Delivery-attempt scoped public tracking. Never serialize internal models."""

import hashlib
import json
import math
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.auth import Db, Operator
from app.config import get_settings
from app.database import audit
from app.deliveries import lock_delivery
from app.gps import freshness
from app.routing_provider import RoutingProvider, RoutingUnavailable
from app.tracking_security import new_token, rate_limit, token_hash

router = APIRouter(prefix="/api/v1", tags=["customer-tracking"])
ACTIVE = {"EN_ROUTE", "ARRIVED", "DELIVERING"}


class CreateLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delivery_id: UUID


class LinkCreated(BaseModel):
    id: UUID
    url: str
    expires_at: datetime | None


class LinkRevoked(BaseModel):
    id: UUID
    revoked_at: datetime


class PublicGps(BaseModel):
    latitude: float
    longitude: float
    updated_at: datetime
    freshness: Literal["NORMAL", "STALE", "LOST"]


class PublicTracking(BaseModel):
    code: str
    status: str
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    gps: PublicGps | None = None
    eta_at: datetime | None = None
    eta_status: Literal["AVAILABLE", "UNKNOWN", "COMPLETED"] = "UNKNOWN"


@router.post("/tracking-links", response_model=LinkCreated, status_code=201)
def create_link(data: CreateLink, user: Operator, request: Request, db: Db) -> LinkCreated:
    value = lock_delivery(db, data.delivery_id, user)
    if value.status not in ACTIVE or value.trip_id is None:
        raise HTTPException(409, "Chỉ tạo link cho lượt đang giao")
    stop = (
        db.execute(
            text("""SELECT s.id,t.vehicle_id FROM trip_stops s
        JOIN trips t ON t.id=s.trip_id WHERE s.delivery_id=:delivery AND s.trip_id=:trip
        AND t.status='ACTIVE'"""),
            {"delivery": value.id, "trip": value.trip_id},
        )
        .mappings()
        .first()
    )
    if stop is None:
        raise HTTPException(409, "Lượt giao chưa hoạt động")
    base = get_settings().tracking_public_base_url.rstrip("/")
    parsed = urlsplit(base)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path
    ):
        raise HTTPException(503, "Thiếu/sai cấu hình URL tracking")
    raw, digest = new_token()
    identifier = uuid4()
    db.execute(
        text("""INSERT INTO tracking_tokens
        (id,delivery_id,token_hash,trip_stop_id,vehicle_id,created_by,expires_at)
        VALUES (:id,:delivery,:hash,:stop,:vehicle,:actor,NULL)"""),
        {
            "id": identifier,
            "delivery": value.id,
            "hash": digest,
            "stop": stop["id"],
            "vehicle": stop["vehicle_id"],
            "actor": user.id,
        },
    )
    audit(
        db,
        request,
        user.id,
        "CREATE",
        "tracking_link",
        identifier,
        after={"delivery_id": str(value.id), "trip_stop_id": str(stop["id"])},
    )
    return LinkCreated(id=identifier, url=f"{base}/t/{raw}", expires_at=None)


@router.post("/tracking-links/{identifier}/revoke", response_model=LinkRevoked)
def revoke_link(identifier: UUID, user: Operator, request: Request, db: Db) -> LinkRevoked:
    db.execute(text("SELECT pg_advisory_xact_lock(73210402)"))
    row = (
        db.execute(
            text("""SELECT * FROM tracking_tokens WHERE id=:id FOR UPDATE"""), {"id": identifier}
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Không tìm thấy link")
    if row["revoked_at"] is not None:
        return LinkRevoked(id=identifier, revoked_at=row["revoked_at"])
    now = db.scalar(text("SELECT now()"))
    db.execute(
        text("UPDATE tracking_tokens SET revoked_at=:now WHERE id=:id"),
        {"now": now, "id": identifier},
    )
    audit(
        db,
        request,
        user.id,
        "REVOKE",
        "tracking_link",
        identifier,
        after={"reason": "STAFF_REVOKED"},
    )
    return LinkRevoked(id=identifier, revoked_at=now)


def estimated_arrival(
    db: Connection, row: Any, gps: PublicGps, now: datetime, redis: Redis
) -> datetime | None:
    if gps.freshness != "NORMAL":
        return None
    stops = (
        db.execute(
            text("""SELECT s.id,s.sequence_no,s.status FROM trip_stops s
        WHERE trip_id=:trip AND sequence_no<=:sequence AND
        status NOT IN ('DELIVERED','FAILED','CANCELLED') ORDER BY sequence_no"""),
            {"trip": row["trip_id"], "sequence": row["sequence_no"]},
        )
        .mappings()
        .all()
    )
    plan = (
        db.execute(
            text("""SELECT id,result_json FROM trip_route_plans WHERE trip_id=:trip
        AND approved_at IS NOT NULL ORDER BY approved_at DESC LIMIT 1"""),
            {"trip": row["trip_id"]},
        )
        .mappings()
        .first()
    )
    if not plan or not stops or stops[-1]["id"] != row["trip_stop_id"]:
        return None
    key_data = [
        str(plan["id"]),
        gps.model_dump(mode="json"),
        [(str(s["id"]), s["status"]) for s in stops],
    ]
    key = "tracking:eta:" + hashlib.sha256(json.dumps(key_data).encode()).hexdigest()
    try:
        cached = redis.get(key)
        if cached:
            return datetime.fromisoformat(str(cached))
        approved = {s["stop_id"]: s for s in plan["result_json"]["stops"]}
        details = [approved[str(s["id"])] for s in stops]
        points = [(gps.latitude, gps.longitude)] + [
            (s["latitude"], s["longitude"]) for s in details
        ]
        matrix = RoutingProvider(get_settings()).matrix(points)
        arrival = now
        for index, detail in enumerate(details):
            duration = matrix.durations_s[index][index + 1]
            if duration is None:
                return None
            arrival += timedelta(seconds=duration)
            lower = detail.get("window_start")
            if lower:
                arrival = max(arrival, datetime.fromisoformat(lower))
            if index < len(details) - 1:
                arrival += timedelta(seconds=detail["service_seconds"])
        redis.setex(key, 10, arrival.isoformat())
        return arrival
    except (RedisError, RoutingUnavailable, ValueError, KeyError, TypeError):
        return None


@router.get(
    "/public/tracking/{token}",
    response_model=PublicTracking,
    responses={410: {"description": "Link expired, revoked or invalid"}},
)
def public_tracking(token: str, request: Request, db: Db) -> PublicTracking:
    settings = get_settings()
    with Redis.from_url(
        settings.redis_url.get_secret_value(),
        decode_responses=True,
        socket_timeout=2,
        socket_connect_timeout=2,
    ) as redis:
        peer = hashlib.sha256(
            (request.client.host if request.client else "unknown").encode()
        ).hexdigest()
        rate_limit(redis, "tracking:peer:" + peer, settings.tracking_peer_requests_per_minute)
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise HTTPException(410, "Liên kết không còn hiệu lực")
        digest = token_hash(token)
        rate_limit(redis, "tracking:token:" + digest, settings.tracking_token_requests_per_minute)
        # Mutations use the exclusive M4 lock; concurrent readers share it. Acquire before
        # row locks to preserve the existing transaction order and avoid revoke/start deadlocks.
        db.execute(text("SELECT pg_advisory_xact_lock_shared(73210402)"))
        # Share locks keep lifecycle/assignment stable until the response has been computed.
        row = (
            db.execute(
                text("""SELECT k.*,d.code,d.status,s.trip_id,s.sequence_no,
            t.vehicle_id AS current_vehicle,t.status AS trip_status
            FROM tracking_tokens k JOIN deliveries d ON d.id=k.delivery_id
            JOIN trip_stops s ON s.id=k.trip_stop_id AND s.delivery_id=d.id
            JOIN trips t ON t.id=s.trip_id WHERE k.token_hash=:hash AND s.trip_id=
            (SELECT latest.id FROM trip_stops cs JOIN trips latest ON latest.id=cs.trip_id
             WHERE cs.delivery_id=d.id ORDER BY latest.created_at DESC,latest.id DESC LIMIT 1)
            FOR SHARE OF k,d,s,t"""),
                {"hash": digest},
            )
            .mappings()
            .first()
        )
        now = datetime.now(UTC)
        if (
            row is None
            or row["revoked_at"] is not None
            or row["vehicle_id"] != row["current_vehicle"]
            or row["status"] not in ACTIVE | {"DELIVERED"}
            or (row["expires_at"] is not None and now >= row["expires_at"])
            or (row["status"] != "DELIVERED" and row["trip_status"] != "ACTIVE")
        ):
            raise HTTPException(410, "Liên kết không còn hiệu lực")
        result = PublicTracking(
            code=row["code"], status=row["status"], expires_at=row["expires_at"]
        )
        if row["status"] == "DELIVERED":
            if row["expires_at"] is None:
                raise HTTPException(410, "Liên kết không còn hiệu lực")
            result.completed_at = row["expires_at"] - timedelta(hours=1)
            result.eta_status = "COMPLETED"
            return result
        snapshot = (
            db.execute(
                text("SELECT * FROM gps_snapshots WHERE vehicle_id=:id"), {"id": row["vehicle_id"]}
            )
            .mappings()
            .first()
        )
        if snapshot and all(
            snapshot[field] is not None
            for field in ("latitude", "longitude", "gps_at", "server_received_at")
        ):
            lat, lon = snapshot["latitude"], snapshot["longitude"]
            if (
                math.isfinite(lat)
                and math.isfinite(lon)
                and -90 <= lat <= 90
                and -180 <= lon <= 180
                and snapshot["gps_at"] <= now
                and snapshot["server_received_at"] <= now
            ):
                result.gps = PublicGps(
                    latitude=lat,
                    longitude=lon,
                    updated_at=snapshot["gps_at"],
                    freshness=cast(
                        Literal["NORMAL", "STALE", "LOST"],
                        freshness(snapshot["gps_at"], snapshot["server_received_at"], now),
                    ),
                )
                result.eta_at = estimated_arrival(db, row, result.gps, now, redis)
                if result.eta_at is not None:
                    result.eta_status = "AVAILABLE"
        return result

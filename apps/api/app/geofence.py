"""ROUT-04 / DEC-034: server-side Traccar geofence, hysteresis after correction."""

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.auth import Db, User
from app.database import audit
from app.deliveries import delivery, event, lock_delivery, public
from app.delivery_schemas import DeliveryOut
from app.schemas import Input

router = APIRouter(prefix="/api/v1", tags=["geofence-correction"])


class ArrivalCorrection(Input):
    arrival_event_id: UUID
    reason: str = Field(min_length=1, max_length=2000)


def process_position(db: Connection, vehicle_id: UUID, position: dict[str, Any]) -> None:
    from app.gps import freshness

    if (
        not position["valid"]
        or freshness(position["gps_at"], position["server_received_at"], datetime.now(UTC))
        != "NORMAL"
    ):
        return
    # Caller holds the same global lock as all delivery/trip commands.
    candidates = (
        db.execute(
            text("""SELECT s.*,t.vehicle_id FROM trips t
      JOIN LATERAL (SELECT * FROM trip_stops WHERE trip_id=t.id
        AND status NOT IN ('DELIVERED','FAILED','CANCELLED') ORDER BY sequence_no LIMIT 1) s ON true
      WHERE t.vehicle_id=:vehicle AND t.status='ACTIVE'"""),
            {"vehicle": vehicle_id},
        )
        .mappings()
        .all()
    )
    if len(candidates) != 1:
        if len(candidates) > 1:
            logging.getLogger("fleet").warning(
                "Ambiguous active trips; geofence skipped vehicle=%s", vehicle_id
            )
        return
    stop = candidates[0]
    if stop["status"] != "EN_ROUTE":
        return
    state = (
        db.execute(
            text("SELECT * FROM stop_geofence_state WHERE stop_id=:id FOR UPDATE"),
            {"id": stop["id"]},
        )
        .mappings()
        .first()
    )
    gps_at = position["gps_at"]
    en_route_at = db.scalar(
        text("""SELECT max(event_time) FROM delivery_status_events
        WHERE delivery_id=:id AND to_status='EN_ROUTE'"""),
        {"id": stop["delivery_id"]},
    )
    if en_route_at and gps_at <= en_route_at:
        return
    if state and (
        gps_at <= state["last_gps_at"]
        or (state["corrected_at"] and gps_at <= state["corrected_at"])
    ):
        return
    distance = db.scalar(
        text("""SELECT ST_Distance(location,
      ST_SetSRID(ST_MakePoint(:lon,:lat),4326)::geography) FROM deliveries WHERE id=:id"""),
        {"id": stop["delivery_id"], "lat": position["latitude"], "lon": position["longitude"]},
    )
    if distance is None:
        return
    blocked = bool(state and state["blocked"])
    if blocked and distance > 70:
        blocked = False
    db.execute(
        text("""INSERT INTO stop_geofence_state(stop_id,blocked,last_gps_at)
      VALUES(:id,:blocked,:gps) ON CONFLICT(stop_id) DO UPDATE SET
      blocked=excluded.blocked,last_gps_at=excluded.last_gps_at"""),
        {"id": stop["id"], "blocked": blocked, "gps": gps_at},
    )
    if blocked or distance > 50:
        return
    request_id = f"traccar-geofence:{vehicle_id}:{position['position_id']}"
    db.execute(
        text("""INSERT INTO delivery_status_events
      (delivery_id,from_status,to_status,event_time,source,reason,location,request_id)
      VALUES(:id,'EN_ROUTE','ARRIVED',:gps,'GEOFENCE','Xe vào bán kính 50m',
        ST_SetSRID(ST_MakePoint(:lon,:lat),4326)::geography,:request)"""),
        {
            "id": stop["delivery_id"],
            "gps": gps_at,
            "lat": position["latitude"],
            "lon": position["longitude"],
            "request": request_id,
        },
    )
    db.execute(
        text("UPDATE deliveries SET status='ARRIVED',updated_at=now() WHERE id=:id"),
        {"id": stop["delivery_id"]},
    )
    db.execute(
        text("UPDATE trip_stops SET status='ARRIVED',arrived_at=:gps WHERE id=:id"),
        {"id": stop["id"], "gps": gps_at},
    )
    db.execute(
        text("""INSERT INTO audit_logs
        (action,resource_type,resource_id,before_json,after_json,reason,request_id)
      VALUES('AUTO_ARRIVED','delivery',:id,'{"status":"EN_ROUTE"}',CAST(:after AS jsonb),
        'Xe vào bán kính 50m',:request)"""),
        {
            "id": str(stop["delivery_id"]),
            "after": json.dumps(
                {
                    "status": "ARRIVED",
                    "gps_at": gps_at.isoformat(),
                    "position_id": position["position_id"],
                    "distance_m": distance,
                }
            ),
            "request": request_id,
        },
    )


@router.post("/deliveries/{delivery_id}/arrival-correction", response_model=DeliveryOut)
def correct_arrival(
    delivery_id: UUID, data: ArrivalCorrection, user: User, request: Request, db: Db
) -> DeliveryOut:
    before = lock_delivery(db, delivery_id, user)
    if before.status != "ARRIVED":
        raise HTTPException(409, "Chỉ sửa ARRIVED nhận sai; tải lại đơn")
    latest = db.scalar(
        text("""SELECT id FROM delivery_status_events WHERE delivery_id=:id
      ORDER BY event_time DESC,id DESC LIMIT 1"""),
        {"id": delivery_id},
    )
    if latest != data.arrival_event_id:
        raise HTTPException(409, "Lần ARRIVED đã thay đổi; tải lại trước khi sửa")
    stop = db.execute(
        text("""SELECT s.id FROM trip_stops s JOIN trips t ON t.id=s.trip_id
      WHERE s.delivery_id=:id AND t.id=:trip AND t.status='ACTIVE' AND s.status='ARRIVED'"""),
        {"id": delivery_id, "trip": before.trip_id},
    ).first()
    if stop is None:
        raise HTTPException(409, "Chỉ sửa điểm của chuyến ACTIVE")
    db.execute(
        text("""INSERT INTO stop_geofence_state(stop_id,blocked,last_gps_at,corrected_at)
      VALUES(:id,true,clock_timestamp(),clock_timestamp()) ON CONFLICT(stop_id) DO UPDATE SET
      blocked=true,last_gps_at=excluded.last_gps_at,corrected_at=excluded.corrected_at"""),
        {"id": stop[0]},
    )
    event(db, request, user, delivery_id, "ARRIVED", "EN_ROUTE", data.reason)
    db.execute(
        text("UPDATE trip_stops SET status='EN_ROUTE',arrived_at=NULL WHERE id=:id"),
        {"id": stop[0]},
    )
    result = delivery(db, delivery_id, user)
    audit(
        db,
        request,
        user.id,
        "CORRECT_ARRIVED",
        "delivery",
        delivery_id,
        public(before),
        public(result),
    )
    db.execute(
        text("""UPDATE audit_logs SET reason=:reason WHERE request_id=:request
      AND action='CORRECT_ARRIVED' AND resource_id=:id"""),
        {"reason": data.reason, "request": request.state.request_id, "id": str(delivery_id)},
    )
    return result

"""M4 driver cache payload and durable offline command replay."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text

from app.auth import Db, User
from app.deliveries import change_status, detail_delivery, reschedule, start_trip, trip_detail
from app.delivery_schemas import (
    DeliveryDetailOut,
    DeliveryOut,
    RescheduleInput,
    RescheduleOut,
    StatusCommand,
    TripOut,
)
from app.geofence import ArrivalCorrection, correct_arrival
from app.schemas import Input

router = APIRouter(prefix="/api/v1/driver", tags=["driver-offline"])


class StartAction(Input):
    kind: Literal["START_TRIP"]
    resource_id: UUID


class StatusAction(Input):
    kind: Literal["STATUS"]
    resource_id: UUID
    data: StatusCommand


class RescheduleAction(Input):
    kind: Literal["PROPOSE_RESCHEDULE"]
    resource_id: UUID
    data: RescheduleInput


class CorrectionAction(Input):
    kind: Literal["CORRECT_ARRIVED"]
    resource_id: UUID
    data: ArrivalCorrection


Action = Annotated[
    StartAction | StatusAction | RescheduleAction | CorrectionAction, Field(discriminator="kind")
]


class OfflineCommand(Input):
    client_action_id: UUID
    occurred_at: datetime
    action: Action

    @model_validator(mode="after")
    def aware(self) -> "OfflineCommand":
        if self.occurred_at.tzinfo is None:
            raise ValueError("Thời điểm thao tác cần timezone")
        return self


class DriverRouteStop(BaseModel):
    distance_m: float
    violation: Literal["EARLY", "LATE"] | None
    window_end: datetime | None


class DriverGps(BaseModel):
    freshness: Literal["NORMAL", "STALE", "LOST"]
    gps_at: datetime | None


class DriverToday(BaseModel):
    trips: list[TripOut]
    deliveries: dict[str, DeliveryDetailOut]
    route_stops: dict[str, DriverRouteStop]
    gps: dict[str, DriverGps]


@router.get("/today", response_model=DriverToday)
def today(user: User, db: Db) -> dict[str, Any]:
    from app.deliveries import LOCAL

    if user.role != "DRIVER":
        raise HTTPException(403, "Chỉ tài xế được dùng màn hình chuyến của mình")
    ids: Any = db.execute(
        text("""SELECT t.id FROM trips t JOIN driver_profiles p ON p.id=t.driver_id
      WHERE p.user_id=:user AND p.active AND
      (t.status='ACTIVE' OR (t.trip_date=:date AND t.status IN ('PLANNED','COMPLETED')))
      ORDER BY t.created_at,t.id"""),
        {"user": user.id, "date": datetime.now(LOCAL).date()},
    ).scalars()
    trips = [trip_detail(db, identifier, user) for identifier in ids]
    details = {
        str(stop["delivery_id"]): detail_delivery(UUID(str(stop["delivery_id"])), user, db)
        for trip in trips
        for stop in trip.stops
    }
    route_stops, gps = {}, {}
    for trip in trips:
        plan = db.scalar(
            text("""SELECT result_json FROM trip_route_plans
          WHERE trip_id=:id AND approved_at IS NOT NULL
          ORDER BY approved_at DESC,id DESC LIMIT 1"""),
            {"id": trip.id},
        )
        if plan:
            for index, stop in enumerate(plan["stops"]):
                route_stops[stop["delivery_id"]] = {
                    "distance_m": plan["route_detail"]["legs"][index]["distance"],
                    "violation": stop["violation"],
                    "window_end": stop["window_end"],
                }
        snapshot = (
            db.execute(
                text("SELECT gps_at,server_received_at FROM gps_snapshots WHERE vehicle_id=:id"),
                {"id": trip.vehicle_id},
            )
            .mappings()
            .first()
        )
        from app.gps import freshness

        gps[str(trip.id)] = {
            "freshness": freshness(
                snapshot["gps_at"], snapshot["server_received_at"], datetime.now(UTC)
            )
            if snapshot
            else "LOST",
            "gps_at": snapshot["gps_at"] if snapshot else None,
        }
    return {"trips": trips, "deliveries": details, "route_stops": route_stops, "gps": gps}


@router.post("/actions", response_model=TripOut | DeliveryOut | RescheduleOut)
def offline_action(command: OfflineCommand, user: User, request: Request, db: Db) -> JSONResponse:
    if user.role != "DRIVER":
        raise HTTPException(403, "Chỉ tài xế được đồng bộ thao tác offline")
    digest = hashlib.sha256(command.model_dump_json().encode()).hexdigest()
    # Shared mutation lock gives receipt + business writes a single serializable boundary.
    db.execute(text("SELECT pg_advisory_xact_lock(73210402)"))
    values = {"actor": user.id, "id": command.client_action_id}
    old = (
        db.execute(
            text(
                "SELECT * FROM driver_action_receipts WHERE actor_user_id=:actor "
                "AND client_action_id=:id"
            ),
            values,
        )
        .mappings()
        .first()
    )
    if old:
        if old["command_hash"] != digest:
            raise HTTPException(409, "client_action_id đã dùng cho thao tác khác")
        return JSONResponse(old["response_json"], status_code=old["response_status"])
    action = command.action
    status = 200
    result: Any
    try:
        with db.begin_nested():
            if isinstance(action, StartAction):
                result = start_trip(action.resource_id, user, request, db)
            elif isinstance(action, StatusAction):
                result = change_status(action.resource_id, action.data, user, request, db)
            elif isinstance(action, CorrectionAction):
                result = correct_arrival(action.resource_id, action.data, user, request, db)
            else:
                result = reschedule(action.resource_id, action.data, user, request, db)
            body = jsonable_encoder(result)
            # Trace the stable offline action without replacing server event time.
            db.execute(
                text("""UPDATE audit_logs SET after_json=after_json || CAST(:metadata AS jsonb)
              WHERE actor_user_id=:actor AND request_id=:request"""),
                {
                    "metadata": json.dumps(
                        {
                            "client_action_id": str(command.client_action_id),
                            "client_occurred_at": command.occurred_at.isoformat(),
                        }
                    ),
                    "actor": user.id,
                    "request": request.state.request_id,
                },
            )
    except HTTPException as error:
        status, body = error.status_code, {"detail": error.detail}
        if status >= 500:
            return JSONResponse(body, status_code=status)
    db.execute(
        text("""INSERT INTO driver_action_receipts
       (actor_user_id,client_action_id,command_hash,response_status,response_json)
       VALUES (:actor,:id,:hash,:status,CAST(:body AS jsonb))"""),
        {**values, "hash": digest, "status": status, "body": json.dumps(body)},
    )
    return JSONResponse(body, status_code=status)

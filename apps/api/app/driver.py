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
from app.database import audit
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
from app.pod_metadata import PodMetadata
from app.pod_schemas import PodPhotoOut
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


class PodAction(Input):
    kind: Literal["POD_UPLOAD"]
    resource_id: UUID
    data: PodMetadata


Action = Annotated[
    StartAction | StatusAction | RescheduleAction | CorrectionAction | PodAction,
    Field(discriminator="kind"),
]


class OfflineCommand(Input):
    client_action_id: UUID
    occurred_at: datetime
    action: Action
    replaces_client_action_id: UUID | None = None

    @model_validator(mode="after")
    def aware(self) -> "OfflineCommand":
        if self.occurred_at.tzinfo is None:
            raise ValueError("Thời điểm thao tác cần timezone")
        if (
            isinstance(self.action, PodAction)
            and self.action.data.client_action_id != self.client_action_id
        ):
            raise ValueError("POD phải giữ cùng client_action_id của command")
        return self


def command_digest(command: OfflineCommand) -> str:
    # Keep hashes of commands persisted before DEC-036 byte-compatible.
    excluded = {"replaces_client_action_id"} if command.replaces_client_action_id is None else set()
    return hashlib.sha256(command.model_dump_json(exclude=excluded).encode()).hexdigest()


class ConflictReview(BaseModel):
    review_token: str
    state: dict[str, Any]
    conflict: str


class ConflictResolution(Input):
    command: OfflineCommand
    review_token: str = Field(min_length=64, max_length=64)
    reason: str = Field(min_length=1, max_length=1000)
    decided_at: datetime

    @model_validator(mode="after")
    def valid(self) -> "ConflictResolution":
        if not self.reason.strip() or self.decided_at.tzinfo is None:
            raise ValueError("Cần lý do và thời điểm có timezone")
        return self


class ConflictResolved(BaseModel):
    client_action_id: UUID
    state: Literal["DISCARDED"] = "DISCARDED"


def conflict_receipt(command: OfflineCommand, user: User, db: Db) -> Any:
    if user.role != "DRIVER":
        raise HTTPException(403, "Chỉ tài xế được xử lý conflict của mình")
    receipt = (
        db.execute(
            text(
                "SELECT * FROM driver_action_receipts WHERE actor_user_id=:actor "
                "AND client_action_id=:id"
            ),
            {"actor": user.id, "id": command.client_action_id},
        )
        .mappings()
        .first()
    )
    if receipt is None or receipt["response_status"] != 409:
        raise HTTPException(404, "Không tìm thấy conflict của tài xế")
    if receipt["command_hash"] != command_digest(command):
        raise HTTPException(409, "Command gốc không khớp receipt; không được sửa payload")
    return receipt


def conflict_state(command: OfflineCommand, user: User, db: Db) -> dict[str, Any]:
    action = command.action
    try:
        if isinstance(action, StartAction):
            trip_state: dict[str, Any] = jsonable_encoder(trip_detail(db, action.resource_id, user))
            return trip_state
        detail = detail_delivery(action.resource_id, user, db)
        return {
            "delivery": jsonable_encoder(detail["delivery"]),
            "latest_event_id": str(detail["events"][-1]["id"]) if detail["events"] else None,
        }
    except HTTPException as error:
        if error.status_code not in {403, 404}:
            raise
        # Historical receipt permits resolving the old command, never reading another driver's data.
        return {"status": "NO_LONGER_ASSIGNED", "resource_id": str(action.resource_id)}


def review_digest(command: OfflineCommand, user: User, state: dict[str, Any]) -> str:
    value = {"actor": str(user.id), "command": command_digest(command), "state": state}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def conflict_audit(
    db: Db,
    request: Request,
    user: User,
    command: OfflineCommand,
    action: str,
    reason: str,
    after: dict[str, Any],
) -> None:
    audit(
        db,
        request,
        user.id,
        action,
        "driver_action",
        command.client_action_id,
        jsonable_encoder(command, exclude_unset=True),
        after,
    )
    db.execute(
        text("""UPDATE audit_logs SET reason=:reason WHERE actor_user_id=:actor
      AND request_id=:request AND resource_type='driver_action'
      AND resource_id=:id AND action=:action"""),
        {
            "reason": reason,
            "actor": user.id,
            "request": request.state.request_id,
            "id": str(command.client_action_id),
            "action": action,
        },
    )


@router.post("/conflicts/review", response_model=ConflictReview)
def review_conflict(command: OfflineCommand, user: User, db: Db) -> ConflictReview:
    db.execute(text("SELECT pg_advisory_xact_lock(73210402)"))
    receipt = conflict_receipt(command, user, db)
    state = conflict_state(command, user, db)
    return ConflictReview(
        review_token=review_digest(command, user, state),
        state=state,
        conflict=str(receipt["response_json"].get("detail", "Dữ liệu đã thay đổi")),
    )


@router.post("/conflicts/resolve", response_model=ConflictResolved)
def resolve_conflict(
    data: ConflictResolution, user: User, request: Request, db: Db
) -> ConflictResolved:
    db.execute(text("SELECT pg_advisory_xact_lock(73210402)"))
    receipt = conflict_receipt(data.command, user, db)
    values = {"actor": user.id, "id": data.command.client_action_id}
    digest = hashlib.sha256(data.model_dump_json().encode()).hexdigest()
    old = (
        db.execute(
            text(
                "SELECT * FROM driver_conflict_resolutions WHERE actor_user_id=:actor "
                "AND client_action_id=:id"
            ),
            values,
        )
        .mappings()
        .first()
    )
    if old:
        if old["resolution_hash"] != digest:
            raise HTTPException(409, "Quyết định đã ghi nhận; không được sửa")
        return ConflictResolved(client_action_id=data.command.client_action_id)
    state = conflict_state(data.command, user, db)
    if data.review_token != review_digest(data.command, user, state):
        raise HTTPException(409, "Dữ liệu lại thay đổi; xem dữ liệu mới trước khi xác nhận bỏ")
    db.execute(
        text("""INSERT INTO driver_conflict_resolutions
      (actor_user_id,client_action_id,resolution_hash,command_json,review_snapshot,reason,decided_at)
      VALUES (:actor,:id,:hash,CAST(:command AS jsonb),CAST(:snapshot AS jsonb),
              :reason,:decided)"""),
        {
            **values,
            "hash": digest,
            "command": json.dumps(jsonable_encoder(data.command, exclude_unset=True)),
            "snapshot": json.dumps(state),
            "reason": data.reason,
            "decided": data.decided_at,
        },
    )
    conflict_audit(
        db,
        request,
        user,
        data.command,
        "OFFLINE_CONFLICT_DISCARDED",
        data.reason,
        {
            "state": "DISCARDED",
            "conflict": receipt["response_json"],
            "review_snapshot": state,
            "client_decided_at": data.decided_at.isoformat(),
        },
    )
    return ConflictResolved(client_action_id=data.command.client_action_id)


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


@router.post("/actions", response_model=TripOut | DeliveryOut | RescheduleOut | PodPhotoOut)
def offline_action(command: OfflineCommand, user: User, request: Request, db: Db) -> JSONResponse:
    if user.role != "DRIVER":
        raise HTTPException(403, "Chỉ tài xế được đồng bộ thao tác offline")
    digest = command_digest(command)
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
    replacement_valid = False
    result: Any
    try:
        with db.begin_nested():
            if command.replaces_client_action_id is not None:
                replacement = (
                    db.execute(
                        text("""SELECT * FROM driver_conflict_resolutions
                  WHERE actor_user_id=:actor AND client_action_id=:old FOR UPDATE"""),
                        {"actor": user.id, "old": command.replaces_client_action_id},
                    )
                    .mappings()
                    .first()
                )
                if (
                    replacement is None
                    or replacement["command_json"]["action"]["resource_id"]
                    != str(action.resource_id)
                    or (replacement["command_json"]["action"]["kind"] == "START_TRIP")
                    != isinstance(action, StartAction)
                ):
                    raise HTTPException(
                        409, "Command thay thế phải liên kết conflict đã bỏ của cùng entity"
                    )
                if replacement["replacement_client_action_id"] is not None:
                    raise HTTPException(409, "Conflict đã có command thay thế")
                replacement_valid = True
            if isinstance(action, StartAction):
                result = start_trip(action.resource_id, user, request, db)
            elif isinstance(action, StatusAction):
                result = change_status(action.resource_id, action.data, user, request, db)
            elif isinstance(action, CorrectionAction):
                result = correct_arrival(action.resource_id, action.data, user, request, db)
            elif isinstance(action, PodAction):
                from app.pod import acknowledge_photo

                result = acknowledge_photo(action.resource_id, action.data, user, db)
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
                            "replaces_client_action_id": str(command.replaces_client_action_id)
                            if command.replaces_client_action_id
                            else None,
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
    if status == 409:
        conflict_audit(
            db,
            request,
            user,
            command,
            "OFFLINE_CONFLICT",
            str(body["detail"]),
            {"state": "CONFLICT", "response": body},
        )
    if replacement_valid:
        # Keep rejected replacement attempts traceable too; exact retries return the receipt above.
        linked = db.execute(
            text("""UPDATE driver_conflict_resolutions SET replacement_client_action_id=:new
          WHERE actor_user_id=:actor AND client_action_id=:old
          AND replacement_client_action_id IS NULL
          AND command_json->'action'->>'resource_id'=:resource RETURNING client_action_id"""),
            {
                "new": command.client_action_id,
                "actor": user.id,
                "old": command.replaces_client_action_id,
                "resource": str(action.resource_id),
            },
        ).scalar()
        if linked:
            conflict_audit(
                db,
                request,
                user,
                command,
                "OFFLINE_CONFLICT_REPLACEMENT",
                "Command mới từ trạng thái đã xem",
                {
                    "old_client_action_id": str(linked),
                    "new_client_action_id": str(command.client_action_id),
                    "response_status": status,
                },
            )
    return JSONResponse(body, status_code=status)

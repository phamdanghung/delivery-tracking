import hashlib
import json
import math
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import text
from sqlalchemy.engine import Connection
from starlette.responses import JSONResponse

from app.auth import Db, Operator
from app.config import get_settings
from app.database import audit, table
from app.deliveries import delivery, event, public, trip_detail
from app.route_optimizer import NoRoute, optimize_route
from app.route_policy import time_window
from app.route_schemas import (
    ApproveInput,
    OptimizeInput,
    RoutePlanOut,
    RouteStopOut,
    RoutingConfigOut,
)
from app.routing_provider import RoutingProvider, RoutingUnavailable

router = APIRouter(prefix="/api/v1", tags=["route-optimization"])


def source(db: Connection, identifier: UUID) -> dict[str, Any]:
    trip = (
        db.execute(
            text("""SELECT t.id,t.trip_date,t.vehicle_id,t.driver_id,t.status,
        ST_Y(t.start_location::geometry) AS start_lat,ST_X(t.start_location::geometry) AS start_lon,
        ST_Y(t.end_location::geometry) AS end_lat,ST_X(t.end_location::geometry) AS end_lon,
        v.status AS vehicle_status,v.max_weight_kg,v.max_volume_m3,p.active AS driver_active,
        u.is_active AS user_active,u.role AS driver_role
        FROM trips t JOIN vehicles v ON v.id=t.vehicle_id
        JOIN driver_profiles p ON p.id=t.driver_id JOIN users u ON u.id=p.user_id
        WHERE t.id=:id"""),
            {"id": identifier},
        )
        .mappings()
        .first()
    )
    if trip is None:
        raise HTTPException(404, "Không tìm thấy chuyến")
    stops = [
        dict(row)
        for row in db.execute(
            text("""SELECT s.id AS stop_id,s.delivery_id,
        s.status AS stop_status,d.status AS delivery_status,d.scheduled_date,d.recipient_name,
        d.address_text,d.commitment_type,d.appointment_at,d.window_start,d.window_end,d.deadline_at,
        d.weight_kg,d.volume_m3,ST_Y(d.location::geometry) AS latitude,
        ST_X(d.location::geometry) AS longitude FROM trip_stops s
        JOIN deliveries d ON d.id=s.delivery_id WHERE s.trip_id=:id ORDER BY s.id"""),
            {"id": identifier},
        ).mappings()
    ]
    return {"trip": dict(trip), "stops": stops}


def draft_ready(value: dict[str, Any]) -> None:
    trip, stops = value["trip"], value["stops"]
    if trip["status"] != "DRAFT":
        raise HTTPException(409, "Chỉ tối ưu/duyệt chuyến nháp")
    if (
        trip["vehicle_status"] != "ACTIVE"
        or not trip["driver_active"]
        or not trip["user_active"]
        or trip["driver_role"] != "DRIVER"
    ):
        raise HTTPException(409, "Xe/tài xế không còn hoạt động")
    if not stops or any(
        s["delivery_status"] != "PLANNED"
        or s["stop_status"] != "PLANNED"
        or s["scheduled_date"] != trip["trip_date"]
        for s in stops
    ):
        raise HTTPException(409, "Điểm giao đã thay đổi trạng thái/ngày; cần điều chỉnh dữ liệu")
    if any(trip[key] is None for key in ("start_lat", "start_lon", "end_lat", "end_lon")) or any(
        s["latitude"] is None or s["longitude"] is None for s in stops
    ):
        raise HTTPException(422, "Thiếu tọa độ điểm đầu/cuối hoặc điểm giao")


def snapshot(
    value: dict[str, Any], data: OptimizeInput, provider: RoutingProvider
) -> dict[str, Any]:
    settings = provider.settings
    return dict(
        jsonable_encoder(
            {
                "source": value,
                "command": data.model_dump(mode="json"),
                "policy": {
                    "tolerance_s": settings.fixed_time_tolerance_seconds,
                    "default_service_s": settings.default_service_seconds,
                },
                "provider": provider.url,
                "dataset": provider.dataset(),
            }
        )
    )


def fingerprint(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def latest(db: Connection, trip_id: UUID) -> Any:
    row = (
        db.execute(
            text("""SELECT * FROM trip_route_plans WHERE trip_id=:trip
        ORDER BY created_at DESC,id DESC LIMIT 1"""),
            {"trip": trip_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(409, "Chuyến chưa có kết quả tối ưu")
    return row


@router.get("/routing/config", response_model=RoutingConfigOut)
def routing_config(user: Operator) -> RoutingConfigOut:
    settings = get_settings()
    message = None
    try:
        RoutingProvider(settings).dataset()
    except RoutingUnavailable as exc:
        message = str(exc)
    return RoutingConfigOut(
        configured=message is None,
        message=message,
        fixed_time_tolerance_seconds=settings.fixed_time_tolerance_seconds,
        default_service_seconds=settings.default_service_seconds,
    )


@router.post(
    "/trips/{trip_id}/optimize",
    response_model=RoutePlanOut,
    responses={
        422: {
            "model": RoutePlanOut,
            "description": "Kết quả đã lưu có vi phạm thời gian; không được duyệt",
        }
    },
)
def optimize(trip_id: UUID, data: OptimizeInput, user: Operator, request: Request, db: Db) -> Any:
    value = source(db, trip_id)
    draft_ready(value)
    stops, trip = value["stops"], value["trip"]
    if set(data.service_seconds) - {s["stop_id"] for s in stops}:
        raise HTTPException(422, "Override service chứa điểm không thuộc chuyến")
    settings = get_settings()
    departure = data.planned_departure_at
    try:
        windows = [
            time_window(
                s,
                departure,
                data.service_seconds.get(s["stop_id"], settings.default_service_seconds),
                settings,
            )
            for s in stops
        ]
        provider = RoutingProvider(settings)
        before = snapshot(value, data, provider)
        points = [
            (trip["start_lat"], trip["start_lon"]),
            *((s["latitude"], s["longitude"]) for s in stops),
            (trip["end_lat"], trip["end_lon"]),
        ]
        matrix = provider.matrix(points)
        solution = optimize_route(
            matrix, tuple(w[0] for w in windows), time_limit_s=settings.route_solver_seconds
        )
        detail = provider.route([points[0], *(points[i] for i in solution.order), points[-1]])
    except RoutingUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except NoRoute as exc:
        raise HTTPException(422, "Không tìm được tuyến đầy đủ; không bỏ điểm giao") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    # No global mutation lock while OSRM/solver run. Recheck under the existing M2 lock.
    db.execute(text("SELECT pg_advisory_xact_lock(73210402)"))
    current = source(db, trip_id)
    draft_ready(current)
    try:
        if fingerprint(snapshot(current, data, provider)) != fingerprint(before):
            raise HTTPException(409, "Dữ liệu/config thay đổi trong lúc tối ưu; chạy lại")
    except RoutingUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    output = []
    for sequence, index in enumerate(solution.order, 1):
        stop = stops[index - 1]
        window, lower, upper = windows[index - 1]
        arrival = departure + timedelta(seconds=solution.arrivals_s[index - 1])
        early = max(0, (lower - arrival).total_seconds()) if lower else 0
        late = max(0, (arrival - upper).total_seconds())
        output.append(
            {
                "stop_id": stop["stop_id"],
                "delivery_id": stop["delivery_id"],
                "sequence_no": sequence,
                "recipient_name": stop["recipient_name"],
                "address_text": stop["address_text"],
                "latitude": stop["latitude"],
                "longitude": stop["longitude"],
                "commitment_type": stop["commitment_type"],
                "window_start": lower,
                "window_end": upper,
                "arrival_at": arrival,
                "service_seconds": window.service_s,
                "violation_seconds": math.ceil(early + late),
                "violation": "EARLY" if early else "LATE" if late else None,
            }
        )
    feasible = not any(s["violation"] for s in output)
    warnings = trip_detail(db, trip_id, user).warnings
    if not all(solution.proven_objectives):
        warnings.append(
            "Đã hết ngân sách giải; chưa chứng minh tối ưu toàn cục các mục tiêu còn lại"
        )
    identifier = uuid4()
    result = RoutePlanOut(
        id=identifier,
        trip_id=trip_id,
        planned_departure_at=departure,
        distance_m=solution.distance_m,
        duration_s=solution.elapsed_s,
        stops=[RouteStopOut.model_validate(s) for s in output],
        geometry=detail["geometry"],
        route_detail=detail,
        warnings=warnings,
        time_feasible=feasible,
        approval_allowed=feasible,
        proven_objectives=solution.proven_objectives,
        solver_seconds=solution.solver_seconds,
        dataset_sha256=before["dataset"],
    )
    db.execute(
        table("trip_route_plans", db)
        .insert()
        .values(
            id=identifier,
            trip_id=trip_id,
            input_fingerprint=fingerprint(before),
            input_json=before,
            result_json=public(result),
            created_by=user.id,
        )
    )
    db.execute(
        text("""UPDATE trips SET planned_departure_at=:departure,
        planned_distance_m=:distance,planned_duration_s=:duration WHERE id=:id"""),
        {
            "id": trip_id,
            "departure": departure,
            "distance": result.distance_m,
            "duration": result.duration_s,
        },
    )
    # Avoid the existing immediate UNIQUE(trip_id, sequence_no) during permutations.
    db.execute(
        text("UPDATE trip_stops SET sequence_no=-sequence_no WHERE trip_id=:id"), {"id": trip_id}
    )
    for stop_result in result.stops:
        db.execute(
            text("""UPDATE trip_stops SET sequence_no=:sequence,
            planned_arrival_at=:arrival,eta_at=:arrival WHERE id=:id"""),
            {
                "id": stop_result.stop_id,
                "sequence": stop_result.sequence_no,
                "arrival": stop_result.arrival_at,
            },
        )
    audit(
        db,
        request,
        user.id,
        "OPTIMIZE",
        "trip",
        trip_id,
        after={
            "plan_id": str(identifier),
            "time_feasible": feasible,
            "distance_m": result.distance_m,
        },
    )
    # Returning 422 rather than raising commits the diagnostic snapshot transaction.
    return result if feasible else JSONResponse(status_code=422, content=public(result))


@router.get("/trips/{trip_id}/optimization", response_model=RoutePlanOut)
def get_optimization(trip_id: UUID, user: Operator, db: Db) -> RoutePlanOut:
    value = source(db, trip_id)
    row = latest(db, trip_id)
    result = RoutePlanOut.model_validate(row["result_json"])
    result.approved = row["approved_at"] is not None
    if result.approved:
        result.approval_allowed = False
        return result
    try:
        data = OptimizeInput.model_validate(row["input_json"]["command"])
        result.stale = (
            fingerprint(snapshot(value, data, RoutingProvider(get_settings())))
            != row["input_fingerprint"]
        )
    except RoutingUnavailable:
        result.stale = True
    result.approval_allowed = (
        result.time_feasible and not result.stale and value["trip"]["status"] == "DRAFT"
    )
    return result


@router.post("/trips/{trip_id}/approve")
def approve(
    trip_id: UUID, data: ApproveInput, user: Operator, request: Request, db: Db
) -> dict[str, Any]:
    db.execute(text("SELECT pg_advisory_xact_lock(73210402)"))
    value = source(db, trip_id)
    draft_ready(value)
    row = latest(db, trip_id)
    if row["id"] != data.plan_id or row["approved_at"] is not None:
        raise HTTPException(409, "Kết quả đã thay đổi/được duyệt; tải lại")
    try:
        command = OptimizeInput.model_validate(row["input_json"]["command"])
        provider = RoutingProvider(get_settings())
        if fingerprint(snapshot(value, command, provider)) != row["input_fingerprint"]:
            raise HTTPException(409, "Kết quả tối ưu đã cũ; chạy lại")
    except RoutingUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    result = RoutePlanOut.model_validate(row["result_json"])
    actual = {s["stop_id"]: s for s in value["stops"]}
    if len(result.stops) != len(actual) or {s.stop_id for s in result.stops} != set(actual):
        raise HTTPException(409, "Kết quả thiếu/trùng điểm giao")
    for stop in result.stops:
        _, lower, upper = time_window(
            actual[stop.stop_id],
            command.planned_departure_at,
            command.service_seconds.get(stop.stop_id, provider.settings.default_service_seconds),
            provider.settings,
        )
        if stop.arrival_at > upper or (lower is not None and stop.arrival_at < lower):
            raise HTTPException(409, "Có vi phạm hard time constraint; điều chỉnh và tối ưu lại")
    if not result.time_feasible:
        raise HTTPException(409, "Kết quả có vi phạm thời gian; không cho duyệt")
    before = trip_detail(db, trip_id, user)
    for stop in result.stops:
        old = delivery(db, stop.delivery_id, user)
        event(db, request, user, stop.delivery_id, "PLANNED", "ASSIGNED", "Duyệt chuyến sau tối ưu")
        db.execute(
            text("UPDATE trip_stops SET status='ASSIGNED' WHERE id=:id"), {"id": stop.stop_id}
        )
        audit(
            db,
            request,
            user.id,
            "ASSIGN",
            "delivery",
            stop.delivery_id,
            public(old),
            public(delivery(db, stop.delivery_id, user)),
        )
    db.execute(text("UPDATE trips SET status='PLANNED' WHERE id=:id"), {"id": trip_id})
    db.execute(
        text("UPDATE trip_route_plans SET approved_at=now(),approved_by=:actor WHERE id=:id"),
        {"actor": user.id, "id": row["id"]},
    )
    audit(
        db,
        request,
        user.id,
        "APPROVE",
        "trip",
        trip_id,
        public(before),
        public(trip_detail(db, trip_id, user)),
    )
    return {"approved": True, "trip_id": trip_id, "plan_id": data.plan_id}

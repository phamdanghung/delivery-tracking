from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from app.auth import Admin, Db, Operator
from app.database import audit, table
from app.fuel import encoded, record
from app.fuel_schemas import Recompute
from app.gps import find_vehicle
from app.operations_policy import outside_hours, safety_transition
from app.safety_schemas import (
    SafetyAlertOut,
    SafetyConfigInput,
    SafetyConfigOut,
    SafetyExceptionInput,
    SafetyExceptionOut,
    SafetyStateInput,
)

router = APIRouter(prefix="/api/v1/safety", tags=["safety"])


@router.get("/configs", response_model=list[SafetyConfigOut])
def configs(user: Operator, db: Db) -> list[dict[str, Any]]:
    vehicles, config = table("vehicles", db), table("safety_configs", db)
    rows = db.execute(
        select(vehicles.c.id, config.c.speed_limit_kmh, config.c.outside_hours_enabled).outerjoin(
            config, config.c.vehicle_id == vehicles.c.id
        )
    ).mappings()
    return [
        {
            "vehicle_id": r["id"],
            "speed_limit_kmh": r["speed_limit_kmh"],
            "outside_hours_enabled": r["outside_hours_enabled"]
            if r["outside_hours_enabled"] is not None
            else True,
        }
        for r in rows
    ]


@router.patch("/configs/{vehicle_id}", response_model=SafetyConfigOut)
def configure(
    vehicle_id: UUID, data: SafetyConfigInput, user: Admin, request: Request, db: Db
) -> Any:
    find_vehicle(db, vehicle_id)
    entity = table("safety_configs", db)
    before = db.execute(select(entity).where(entity.c.vehicle_id == vehicle_id)).mappings().first()
    values = {
        **data.model_dump(exclude={"reason"}),
        "updated_by": user.id,
        "updated_at": datetime.now(UTC),
    }
    statement = insert(entity).values(vehicle_id=vehicle_id, **values)
    row = (
        db.execute(
            statement.on_conflict_do_update(
                index_elements=[entity.c.vehicle_id], set_=values
            ).returning(entity)
        )
        .mappings()
        .one()
    )
    result = SafetyConfigOut.model_validate({k: row[k] for k in SafetyConfigOut.model_fields})
    audit(
        db,
        request,
        user.id,
        "CONFIGURE",
        "safety_config",
        vehicle_id,
        encoded(dict(before)) if before else None,
        {"config": encoded(result), "reason": data.reason},
        reason=data.reason,
    )
    return result


@router.get("/exceptions", response_model=list[SafetyExceptionOut])
def exceptions(user: Operator, db: Db, vehicle_id: UUID | None = None) -> list[dict[str, Any]]:
    entity = table("safety_exceptions", db)
    query = select(entity).order_by(entity.c.from_at.desc())
    if vehicle_id:
        query = query.where(entity.c.vehicle_id == vehicle_id)
    return [dict(r) for r in db.execute(query).mappings()]


@router.post("/exceptions", response_model=SafetyExceptionOut, status_code=201)
def exception_create(data: SafetyExceptionInput, user: Admin, request: Request, db: Db) -> Any:
    find_vehicle(db, data.vehicle_id)
    entity = table("safety_exceptions", db)
    row = (
        db.execute(
            entity.insert().values(**data.model_dump(), created_by=user.id).returning(entity)
        )
        .mappings()
        .one()
    )
    result = SafetyExceptionOut.model_validate(row)
    audit(
        db,
        request,
        user.id,
        "CREATE",
        "safety_exception",
        result.id,
        after=encoded(result),
        reason=data.reason,
    )
    return result


@router.patch("/exceptions/{exception_id}", response_model=SafetyExceptionOut)
def exception_update(
    exception_id: UUID, data: SafetyExceptionInput, user: Admin, request: Request, db: Db
) -> Any:
    before = record(db, "safety_exceptions", exception_id, True)
    if before["deleted_at"] is not None:
        raise HTTPException(409, "Ngoại lệ đã bị hủy")
    find_vehicle(db, data.vehicle_id)
    entity = table("safety_exceptions", db)
    row = (
        db.execute(
            entity.update()
            .where(entity.c.id == exception_id)
            .values(**data.model_dump())
            .returning(entity)
        )
        .mappings()
        .one()
    )
    result = SafetyExceptionOut.model_validate(row)
    audit(
        db,
        request,
        user.id,
        "UPDATE",
        "safety_exception",
        exception_id,
        encoded(before),
        encoded(result),
        reason=data.reason,
    )
    return result


@router.post("/exceptions/{exception_id}/void", response_model=SafetyExceptionOut)
def exception_void(
    exception_id: UUID, data: Recompute, user: Admin, request: Request, db: Db
) -> Any:
    before = record(db, "safety_exceptions", exception_id, True)
    if before["deleted_at"] is not None:
        return SafetyExceptionOut.model_validate(before)
    entity = table("safety_exceptions", db)
    row = (
        db.execute(
            entity.update()
            .where(entity.c.id == exception_id)
            .values(deleted_at=datetime.now(UTC))
            .returning(entity)
        )
        .mappings()
        .one()
    )
    result = SafetyExceptionOut.model_validate(row)
    audit(
        db,
        request,
        user.id,
        "VOID",
        "safety_exception",
        exception_id,
        encoded(before),
        {"exception": encoded(result), "reason": data.reason},
        reason=data.reason,
    )
    return result


@router.get("/alerts", response_model=list[SafetyAlertOut])
def alerts(user: Operator, db: Db, vehicle_id: UUID | None = None) -> list[dict[str, Any]]:
    entity = table("safety_alerts", db)
    query = select(entity).order_by(entity.c.event_time.desc())
    if vehicle_id:
        query = query.where(entity.c.vehicle_id == vehicle_id)
    return [dict(r) for r in db.execute(query).mappings()]


@router.patch("/alerts/{alert_id}/state", response_model=SafetyAlertOut)
def state(alert_id: UUID, data: SafetyStateInput, user: Operator, request: Request, db: Db) -> Any:
    before = record(db, "safety_alerts", alert_id, True)
    if before["status"] != data.from_state:
        raise HTTPException(409, "Cảnh báo đã thay đổi; tải lại trạng thái mới nhất")
    if not safety_transition(data.from_state, data.to_state):
        raise HTTPException(422, "Chỉ NEW → SEEN → RESOLVED")
    now = datetime.now(UTC)
    values: dict[str, Any] = {"status": data.to_state}
    if data.to_state == "SEEN":
        values.update(seen_by=user.id, seen_at=now, acknowledged_by=user.id, acknowledged_at=now)
    else:
        values.update(resolved_by=user.id, resolved_at=now, resolution_reason=data.reason)
    entity = table("safety_alerts", db)
    row = (
        db.execute(
            entity.update().where(entity.c.id == alert_id).values(**values).returning(entity)
        )
        .mappings()
        .one()
    )
    result = SafetyAlertOut.model_validate(row)
    audit(
        db,
        request,
        user.id,
        data.to_state,
        "safety_alert",
        alert_id,
        encoded(SafetyAlertOut.model_validate(before)),
        encoded(result),
        reason=data.reason,
    )
    return result


def incident_audit(db: Connection, action: str, identifier: UUID, value: dict[str, Any]) -> None:
    db.execute(
        table("audit_logs", db)
        .insert()
        .values(
            action=action,
            resource_type="safety_alert",
            resource_id=str(identifier),
            after_json=encoded(value),
        )
    )


def process_safety_position(db: Connection, vehicle_id: UUID, position: dict[str, Any]) -> None:
    # Called inside GPS ingest's shared REST/socket transaction and row/advisory lock.
    if not position["valid"] or position["freshness"] != "NORMAL":
        return
    config_table, exception_table, alert_table = (
        table(n, db) for n in ("safety_configs", "safety_exceptions", "safety_alerts")
    )
    config = (
        db.execute(select(config_table).where(config_table.c.vehicle_id == vehicle_id))
        .mappings()
        .first()
    )
    at, speed, acc = position["gps_at"], Decimal(str(position["speed_kmh"])), position["acc"]
    limit = config["speed_limit_kmh"] if config else None
    enabled = config["outside_hours_enabled"] if config else True
    active = acc is True or speed > 0
    # Missing ACC while stationary cannot prove inactivity or end an episode.
    off_hours: bool | None = (
        (outside_hours(at) and active)
        if (not outside_hours(at) or active or acc is False)
        else None
    )
    conditions: dict[str, bool | None] = {
        "SPEEDING": speed > limit if limit is not None else None,
        "OUTSIDE_HOURS": off_hours if enabled else False,
    }
    applicable: list[str] = list(
        db.execute(
            select(exception_table.c.type).where(
                exception_table.c.vehicle_id == vehicle_id,
                exception_table.c.deleted_at.is_(None),
                exception_table.c.from_at <= at,
                exception_table.c.to_at > at,
            )
        )
        .scalars()
        .all()
    )
    for kind, violating in conditions.items():
        if kind in applicable:
            violating = False
        if violating is None:
            continue
        current = (
            db.execute(
                select(alert_table)
                .where(
                    alert_table.c.vehicle_id == vehicle_id,
                    alert_table.c.type == kind,
                    alert_table.c.incident_ended_at.is_(None),
                    alert_table.c.source_position_id.is_not(None),
                )
                .with_for_update()
            )
            .mappings()
            .first()
        )
        payload = {
            "source": "TRACCAR",
            "position_id": position["position_id"],
            "gps_at": at,
            "speed_kmh": speed,
            "acc": acc,
            "speed_limit_kmh": limit,
        }
        if not violating:
            if current:
                db.execute(
                    alert_table.update()
                    .where(alert_table.c.id == current["id"])
                    .values(incident_ended_at=at, last_event_at=at)
                )
                incident_audit(db, "INCIDENT_ENDED", current["id"], payload)
            continue
        if current:
            db.execute(
                alert_table.update()
                .where(alert_table.c.id == current["id"])
                .values(last_event_at=at, payload_json=encoded(payload))
            )
        else:
            row = (
                db.execute(
                    alert_table.insert()
                    .values(
                        vehicle_id=vehicle_id,
                        type=kind,
                        event_time=at,
                        source_position_id=position["position_id"],
                        last_event_at=at,
                        payload_json=encoded(payload),
                    )
                    .returning(alert_table)
                )
                .mappings()
                .one()
            )
            incident_audit(db, "CREATE", row["id"], payload)

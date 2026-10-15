import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import and_, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from app.auth import Admin, Db, Operator
from app.database import audit, table
from app.fuel import encoded, record
from app.gps import find_vehicle
from app.maintenance_policy import maintenance_status
from app.maintenance_schemas import (
    MaintenanceEventCreate,
    MaintenanceEventOut,
    MaintenanceRuleInput,
    MaintenanceRuleOut,
    MaintenanceRuleUpdate,
    MaintenanceStatusOut,
    OdometerInput,
    OdometerOut,
    VehicleDocumentInput,
    VehicleDocumentOut,
    VehicleDocumentUpdate,
)
from app.operations_policy import LOCAL
from app.vehicle_receipts import bind_receipt

router = APIRouter(prefix="/api/v1", tags=["maintenance"])


def traccar_odometer(
    db: Connection, vehicle_id: UUID, position: dict[str, Any], raw: dict[str, Any]
) -> None:
    if not position["valid"] or position["freshness"] != "NORMAL":
        return
    attributes = raw.get("attributes")
    value = attributes.get("odometer") if isinstance(attributes, dict) else None
    if value is None or isinstance(value, bool):
        return
    try:
        meters = Decimal(str(value))
        if not meters.is_finite() or meters < 0 or meters / 1000 >= Decimal("100000000000"):
            return
    except InvalidOperation:
        return
    entity = table("vehicle_odometer_readings", db)
    statement = insert(entity).values(
        vehicle_id=vehicle_id,
        odometer_km=meters / 1000,
        observed_at=position["gps_at"],
        source="TRACCAR",
        reason="Odometer từ Traccar",
        source_position_id=position["position_id"],
    )
    inserted = db.execute(
        statement.on_conflict_do_nothing(
            index_elements=[entity.c.vehicle_id, entity.c.source_position_id]
        ).returning(entity.c.id)
    ).scalar()
    if inserted:
        db.execute(
            table("audit_logs", db)
            .insert()
            .values(
                action="OBSERVE",
                resource_type="odometer_reading",
                resource_id=str(inserted),
                after_json=encoded(
                    {
                        "source": "TRACCAR",
                        "position_id": position["position_id"],
                        "observed_at": position["gps_at"],
                        "odometer_km": meters / 1000,
                    }
                ),
            )
        )


def today() -> date:
    return datetime.now(LOCAL).date()


@router.get("/maintenance/rules", response_model=list[MaintenanceRuleOut])
def rules(user: Operator, db: Db, vehicle_id: UUID | None = None) -> list[dict[str, Any]]:
    entity = table("maintenance_rules", db)
    query = select(entity).order_by(entity.c.task_type)
    if vehicle_id:
        query = query.where(entity.c.vehicle_id == vehicle_id)
    return [dict(row) for row in db.execute(query).mappings()]


@router.post("/maintenance/rules", response_model=MaintenanceRuleOut, status_code=201)
def rule_create(data: MaintenanceRuleInput, user: Admin, request: Request, db: Db) -> Any:
    find_vehicle(db, data.vehicle_id)
    if data.baseline_date and data.baseline_date > today():
        raise HTTPException(422, "Không nhập mốc bảo dưỡng tương lai")
    entity = table("maintenance_rules", db)
    row = db.execute(entity.insert().values(**data.model_dump()).returning(entity)).mappings().one()
    result = MaintenanceRuleOut.model_validate(row)
    audit(db, request, user.id, "CREATE", "maintenance_rule", result.id, after=encoded(result))
    return result


@router.patch("/maintenance/rules/{rule_id}", response_model=MaintenanceRuleOut)
def rule_update(
    rule_id: UUID, data: MaintenanceRuleUpdate, user: Admin, request: Request, db: Db
) -> Any:
    before = record(db, "maintenance_rules", rule_id, True)
    if data.vehicle_id != before["vehicle_id"] or data.task_type != before["task_type"]:
        raise HTTPException(
            409, "Không đổi xe/loại của rule đã tạo; tạo rule riêng và ngưng rule cũ"
        )
    if data.baseline_date and data.baseline_date > today():
        raise HTTPException(422, "Không nhập mốc bảo dưỡng tương lai")
    entity = table("maintenance_rules", db)
    row = (
        db.execute(
            entity.update()
            .where(entity.c.id == rule_id)
            .values(**data.model_dump(exclude={"reason"}))
            .returning(entity)
        )
        .mappings()
        .one()
    )
    result = MaintenanceRuleOut.model_validate(row)
    audit(
        db,
        request,
        user.id,
        "UPDATE",
        "maintenance_rule",
        rule_id,
        encoded(before),
        {"rule": encoded(result), "reason": data.reason},
        reason=data.reason,
    )
    return result


@router.get("/maintenance/events", response_model=list[MaintenanceEventOut])
def events(user: Operator, db: Db, vehicle_id: UUID | None = None) -> list[dict[str, Any]]:
    entity = table("maintenance_events", db)
    query = select(entity).order_by(entity.c.service_date.desc(), entity.c.created_at.desc())
    if vehicle_id:
        query = query.where(entity.c.vehicle_id == vehicle_id)
    return [dict(row) for row in db.execute(query).mappings()]


@router.post("/maintenance/events", response_model=MaintenanceEventOut, status_code=201)
def event_create(data: MaintenanceEventCreate, user: Admin, request: Request, db: Db) -> Any:
    db.execute(text("SELECT pg_advisory_xact_lock(73210402)"))
    entity = table("maintenance_events", db)
    digest = hashlib.sha256(data.model_dump_json().encode()).hexdigest()
    old = (
        db.execute(
            select(entity).where(
                entity.c.created_by == user.id, entity.c.client_action_id == data.client_action_id
            )
        )
        .mappings()
        .first()
    )
    if old:
        if old["request_hash"] != digest:
            raise HTTPException(409, "client_action_id đã dùng cho bảo dưỡng khác")
        return MaintenanceEventOut.model_validate(old)
    rule = record(db, "maintenance_rules", data.rule_id, True)
    if rule["vehicle_id"] != data.vehicle_id:
        raise HTTPException(422, "Rule không thuộc xe")
    if data.service_date > today():
        raise HTTPException(422, "Không ghi nhận bảo dưỡng chưa diễn ra")
    if data.receipt_metadata and data.receipt_metadata.client_action_id != data.client_action_id:
        raise HTTPException(409, "Chứng từ phải cùng thao tác ghi bảo dưỡng")
    receipt_id = bind_receipt(db, data.receipt_metadata, data.vehicle_id, "MAINTENANCE", user.id)
    row = (
        db.execute(
            entity.insert()
            .values(
                **data.model_dump(exclude={"receipt_metadata"}),
                task_type=rule["task_type"],
                created_by=user.id,
                receipt_id=receipt_id,
                request_hash=digest,
            )
            .returning(entity)
        )
        .mappings()
        .one()
    )
    result = MaintenanceEventOut.model_validate(row)
    audit(db, request, user.id, "CREATE", "maintenance_event", result.id, after=encoded(result))
    return result


@router.get("/maintenance/odometer-readings", response_model=list[OdometerOut])
def readings(user: Operator, db: Db, vehicle_id: UUID | None = None) -> list[dict[str, Any]]:
    entity = table("vehicle_odometer_readings", db)
    query = select(entity).order_by(entity.c.observed_at.desc())
    if vehicle_id:
        query = query.where(entity.c.vehicle_id == vehicle_id)
    return [dict(row) for row in db.execute(query).mappings()]


@router.post("/maintenance/odometer-readings", response_model=OdometerOut, status_code=201)
def reading_create(data: OdometerInput, user: Admin, request: Request, db: Db) -> Any:
    find_vehicle(db, data.vehicle_id)
    if data.observed_at > datetime.now(UTC):
        raise HTTPException(422, "Không nhập odometer tương lai")
    entity = table("vehicle_odometer_readings", db)
    row = (
        db.execute(
            entity.insert()
            .values(**data.model_dump(), source="ADMIN", created_by=user.id)
            .returning(entity)
        )
        .mappings()
        .one()
    )
    result = OdometerOut.model_validate(row)
    audit(
        db,
        request,
        user.id,
        "CREATE",
        "odometer_reading",
        result.id,
        after=encoded(result),
        reason=data.reason,
    )
    return result


@router.get("/maintenance/status", response_model=list[MaintenanceStatusOut])
def statuses(user: Operator, db: Db, vehicle_id: UUID | None = None) -> list[dict[str, Any]]:
    rule_table, event_table, odo_table = (
        table(n, db)
        for n in ("maintenance_rules", "maintenance_events", "vehicle_odometer_readings")
    )
    query = select(rule_table).where(rule_table.c.active.is_(True)).order_by(rule_table.c.task_type)
    if vehicle_id:
        query = query.where(rule_table.c.vehicle_id == vehicle_id)
    result: list[dict[str, Any]] = []
    for rule in db.execute(query).mappings():
        event = (
            db.execute(
                select(event_table)
                .where(
                    or_(
                        event_table.c.rule_id == rule["id"],
                        and_(
                            event_table.c.rule_id.is_(None),
                            event_table.c.vehicle_id == rule["vehicle_id"],
                            event_table.c.task_type == rule["task_type"],
                        ),
                    )
                )
                .order_by(event_table.c.service_date.desc(), event_table.c.created_at.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        odo = (
            db.execute(
                select(odo_table)
                .where(odo_table.c.vehicle_id == rule["vehicle_id"])
                .order_by(
                    odo_table.c.observed_at.desc(),
                    (odo_table.c.source == "TRACCAR").desc(),
                    odo_table.c.created_at.desc(),
                )
                .limit(1)
            )
            .mappings()
            .first()
        )
        result.append(
            {
                "rule": MaintenanceRuleOut.model_validate(rule),
                "odometer": OdometerOut.model_validate(odo) if odo else None,
                "assessment": maintenance_status(
                    dict(rule),
                    dict(event) if event else None,
                    odo["odometer_km"] if odo else None,
                    today(),
                ),
            }
        )
    return result


def document_out(row: Any) -> VehicleDocumentOut:
    remaining = (row["expiry_date"] - today()).days
    state = (
        "OVERDUE"
        if remaining < 0
        else "DUE"
        if remaining == 0
        else "SOON"
        if remaining <= row["lead_days"]
        else "NOT_DUE"
    )
    return VehicleDocumentOut.model_validate(
        {**dict(row), "remaining_days": remaining, "status": state}
    )


@router.get("/vehicle-documents", response_model=list[VehicleDocumentOut])
def documents(user: Operator, db: Db, vehicle_id: UUID | None = None) -> list[VehicleDocumentOut]:
    entity = table("vehicle_documents", db)
    query = select(entity).order_by(entity.c.expiry_date)
    if vehicle_id:
        query = query.where(entity.c.vehicle_id == vehicle_id)
    return [document_out(row) for row in db.execute(query).mappings()]


@router.post("/vehicle-documents", response_model=VehicleDocumentOut, status_code=201)
def document_create(data: VehicleDocumentInput, user: Admin, request: Request, db: Db) -> Any:
    find_vehicle(db, data.vehicle_id)
    entity = table("vehicle_documents", db)
    row = db.execute(entity.insert().values(**data.model_dump()).returning(entity)).mappings().one()
    result = document_out(row)
    audit(db, request, user.id, "CREATE", "vehicle_document", result.id, after=encoded(result))
    return result


@router.patch("/vehicle-documents/{document_id}", response_model=VehicleDocumentOut)
def document_update(
    document_id: UUID, data: VehicleDocumentUpdate, user: Admin, request: Request, db: Db
) -> Any:
    before = record(db, "vehicle_documents", document_id, True)
    find_vehicle(db, data.vehicle_id)
    entity = table("vehicle_documents", db)
    row = (
        db.execute(
            entity.update()
            .where(entity.c.id == document_id)
            .values(**data.model_dump(exclude={"reason"}))
            .returning(entity)
        )
        .mappings()
        .one()
    )
    result = document_out(row)
    audit(
        db,
        request,
        user.id,
        "UPDATE",
        "vehicle_document",
        document_id,
        encoded(before),
        {"document": encoded(result), "reason": data.reason},
        reason=data.reason,
    )
    return result

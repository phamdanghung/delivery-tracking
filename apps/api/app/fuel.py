import hashlib
from datetime import datetime, time
from decimal import Decimal
from fractions import Fraction
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from app.auth import Admin, Db, Operator
from app.database import audit, table
from app.fuel_schemas import (
    FuelEntryCreate,
    FuelEntryInput,
    FuelEntryOut,
    FuelEntryUpdate,
    FuelProfileInput,
    FuelProfileOut,
    Recompute,
    ReconciliationInput,
    ReconciliationOut,
)
from app.fuel_telemetry import telemetry
from app.gps import find_vehicle
from app.operations_policy import (
    FUEL_VARIANCE_LIMIT,
    LOCAL,
    decimal_value,
    exact_variance,
    observed_fuel,
)
from app.vehicle_receipts import bind_receipt

router = APIRouter(prefix="/api/v1/fuel", tags=["fuel"])


def encoded(value: Any) -> Any:
    return jsonable_encoder(value, custom_encoder={Decimal: str})


def record(db: Connection, name: str, identifier: UUID, lock: bool = False) -> dict[str, Any]:
    entity = table(name, db)
    query = select(entity).where(entity.c.id == identifier)
    row = db.execute(query.with_for_update() if lock else query).mappings().first()
    if row is None:
        raise HTTPException(404, "Không tìm thấy bản ghi")
    return dict(row)


@router.get("/profiles", response_model=list[FuelProfileOut])
def profiles(user: Operator, db: Db, vehicle_id: UUID | None = None) -> list[dict[str, Any]]:
    entity = table("fuel_profiles", db)
    query = select(entity).order_by(entity.c.effective_from)
    if vehicle_id:
        query = query.where(entity.c.vehicle_id == vehicle_id)
    return [dict(row) for row in db.execute(query).mappings()]


@router.post("/profiles", response_model=FuelProfileOut, status_code=201)
def profile_create(data: FuelProfileInput, user: Admin, request: Request, db: Db) -> Any:
    find_vehicle(db, data.vehicle_id)
    entity = table("fuel_profiles", db)
    try:
        row = (
            db.execute(entity.insert().values(**data.model_dump()).returning(entity))
            .mappings()
            .one()
        )
    except IntegrityError as exc:
        raise HTTPException(409, "Profile cùng xe không được chồng lấn hiệu lực") from exc
    result = FuelProfileOut.model_validate(row)
    audit(db, request, user.id, "CREATE", "fuel_profile", result.id, after=encoded(result))
    return result


@router.patch("/profiles/{profile_id}", response_model=FuelProfileOut)
def profile_update(
    profile_id: UUID, data: FuelProfileInput, user: Admin, request: Request, db: Db
) -> Any:
    before = record(db, "fuel_profiles", profile_id, True)
    find_vehicle(db, data.vehicle_id)
    entity = table("fuel_profiles", db)
    try:
        row = (
            db.execute(
                entity.update()
                .where(entity.c.id == profile_id)
                .values(**data.model_dump())
                .returning(entity)
            )
            .mappings()
            .one()
        )
    except IntegrityError as exc:
        raise HTTPException(409, "Profile cùng xe không được chồng lấn hiệu lực") from exc
    result = FuelProfileOut.model_validate(row)
    audit(
        db, request, user.id, "UPDATE", "fuel_profile", profile_id, encoded(before), encoded(result)
    )
    return result


def entry_values(db: Connection, data: FuelEntryInput, actor: UUID) -> dict[str, Any]:
    find_vehicle(db, data.vehicle_id)
    if data.trip_id is not None:
        trip = record(db, "trips", data.trip_id)
        if trip["vehicle_id"] != data.vehicle_id:
            raise HTTPException(422, "Chuyến không thuộc xe đã chọn")
    values = data.model_dump(exclude={"receipt_metadata", "client_action_id"})
    if "receipt_metadata" in data.model_fields_set:
        values["receipt_id"] = bind_receipt(
            db, data.receipt_metadata, data.vehicle_id, "FUEL", actor
        )
    return values


@router.get("/entries", response_model=list[FuelEntryOut])
def entries(user: Operator, db: Db, vehicle_id: UUID | None = None) -> list[dict[str, Any]]:
    entity = table("fuel_entries", db)
    query = select(entity).where(entity.c.deleted_at.is_(None)).order_by(entity.c.filled_at.desc())
    if vehicle_id:
        query = query.where(entity.c.vehicle_id == vehicle_id)
    return [dict(row) for row in db.execute(query).mappings()]


@router.post("/entries", response_model=FuelEntryOut, status_code=201)
def entry_create(data: FuelEntryCreate, user: Operator, request: Request, db: Db) -> Any:
    db.execute(text("SELECT pg_advisory_xact_lock(73210402)"))
    entity = table("fuel_entries", db)
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
            raise HTTPException(409, "client_action_id đã dùng cho lần đổ khác")
        return FuelEntryOut.model_validate(old)
    if data.receipt_metadata and data.receipt_metadata.client_action_id != data.client_action_id:
        raise HTTPException(409, "Chứng từ phải cùng thao tác tạo lần đổ")
    row = (
        db.execute(
            entity.insert()
            .values(
                **entry_values(db, data, user.id),
                created_by=user.id,
                client_action_id=data.client_action_id,
                request_hash=digest,
            )
            .returning(entity)
        )
        .mappings()
        .one()
    )
    result = FuelEntryOut.model_validate(row)
    audit(db, request, user.id, "CREATE", "fuel_entry", result.id, after=encoded(result))
    return result


@router.patch("/entries/{entry_id}", response_model=FuelEntryOut)
def entry_update(
    entry_id: UUID, data: FuelEntryUpdate, user: Operator, request: Request, db: Db
) -> Any:
    before = record(db, "fuel_entries", entry_id, True)
    if before["deleted_at"] is not None:
        raise HTTPException(409, "Lần đổ đã bị hủy")
    if data.client_action_id is not None and data.client_action_id != before["client_action_id"]:
        raise HTTPException(409, "Không thay client_action_id của lần đổ gốc")
    if (
        data.vehicle_id != before["vehicle_id"]
        and before["receipt_id"] is not None
        and "receipt_metadata" not in data.model_fields_set
    ):
        raise HTTPException(409, "Đổi xe cần xác nhận bỏ hoặc thay chứng từ cũ")
    source = FuelEntryInput.model_validate(
        data.model_dump(exclude={"reason", "client_action_id"}, exclude_unset=True)
    )
    entity = table("fuel_entries", db)
    row = (
        db.execute(
            entity.update()
            .where(entity.c.id == entry_id)
            .values(**entry_values(db, source, user.id))
            .returning(entity)
        )
        .mappings()
        .one()
    )
    result = FuelEntryOut.model_validate(row)
    audit(
        db,
        request,
        user.id,
        "UPDATE",
        "fuel_entry",
        entry_id,
        encoded(FuelEntryOut.model_validate(before)),
        {"entry": encoded(result), "reason": data.reason},
        reason=data.reason,
    )
    return result


@router.post("/entries/{entry_id}/void", response_model=FuelEntryOut)
def entry_void(entry_id: UUID, data: Recompute, user: Operator, request: Request, db: Db) -> Any:
    before = record(db, "fuel_entries", entry_id, True)
    if before["deleted_at"] is not None:
        return FuelEntryOut.model_validate(before)
    from datetime import UTC

    entity = table("fuel_entries", db)
    row = (
        db.execute(
            entity.update()
            .where(entity.c.id == entry_id)
            .values(deleted_at=datetime.now(UTC))
            .returning(entity)
        )
        .mappings()
        .one()
    )
    result = FuelEntryOut.model_validate(row)
    audit(
        db,
        request,
        user.id,
        "VOID",
        "fuel_entry",
        entry_id,
        encoded(FuelEntryOut.model_validate(before)),
        {"entry": encoded(result), "reason": data.reason},
        reason=data.reason,
    )
    return result


def calculate(db: Connection, period: dict[str, Any]) -> dict[str, Any]:
    start, end, vehicle_id = period["from_at"], period["to_at"], period["vehicle_id"]
    vehicle = find_vehicle(db, vehicle_id)
    profile_table, entry_table = table("fuel_profiles", db), table("fuel_entries", db)
    profiles = (
        db.execute(
            select(profile_table)
            .where(profile_table.c.vehicle_id == vehicle_id)
            .order_by(profile_table.c.effective_from)
        )
        .mappings()
        .all()
    )
    entries = (
        db.execute(
            select(entry_table)
            .where(
                entry_table.c.vehicle_id == vehicle_id,
                entry_table.c.deleted_at.is_(None),
                entry_table.c.filled_at >= start,
                entry_table.c.filled_at < end,
            )
            .order_by(entry_table.c.filled_at)
        )
        .mappings()
        .all()
    )
    actual = sum((row["liters"] for row in entries), Decimal("0"))
    cost = sum((row["amount"] or Decimal("0") for row in entries), Decimal("0"))
    cursor, expected = start, Fraction(0)
    reasons: list[str] = []
    segments: list[dict[str, Any]] = []
    for profile in profiles:
        first = datetime.combine(profile["effective_from"], time(), LOCAL)
        last = (
            datetime.combine(profile["effective_to"], time(), LOCAL)
            if profile["effective_to"]
            else end
        )
        first, last = max(first, start), min(last, end)
        if first >= last:
            continue
        if first > cursor:
            reasons.append("FUEL_PROFILE_GAP")
        observed = telemetry(
            vehicle["traccar_device_id"], first, last, profile["idling_l_per_hour"] > 0
        )
        segment: dict[str, Any] = {
            "from_at": first,
            "to_at": last,
            "profile": FuelProfileOut.model_validate(profile).model_dump(),
            **observed,
        }
        if observed["reasons"]:
            reasons.extend(observed["reasons"])
            segment["expected_liters"] = None
        else:
            value = observed_fuel(
                observed["distance_km"],
                observed["idle_seconds"] if profile["idling_l_per_hour"] > 0 else Decimal("0"),
                profile["driving_l_per_100km"],
                profile["idling_l_per_hour"],
            )
            segment["expected_liters"] = decimal_value(value)
            expected += value
        segments.append(segment)
        cursor = last
    if cursor < end:
        reasons.append("FUEL_PROFILE_GAP")
    if not reasons and expected <= 0:
        reasons.append("EXPECTED_NONPOSITIVE")
    result: dict[str, Any] = encoded(
        {
            "data_status": "INSUFFICIENT" if reasons else "COMPLETE",
            "reasons": sorted(set(reasons)),
            "actual_liters": actual,
            "actual_cost": cost if all(e["amount"] is not None for e in entries) else None,
            "known_cost": cost,
            "cost_complete": all(e["amount"] is not None for e in entries),
            "expected_liters": None if reasons else decimal_value(expected),
            "variance_pct": None if reasons else decimal_value(exact_variance(actual, expected)),
            "alert_flag": False
            if reasons
            else abs(exact_variance(actual, expected)) > Fraction(FUEL_VARIANCE_LIMIT),
            "entries": [FuelEntryOut.model_validate(row).model_dump() for row in entries],
            "segments": segments,
        }
    )
    return result


def period_out(db: Connection, row: dict[str, Any]) -> ReconciliationOut:
    versions = table("fuel_reconciliation_versions", db)
    history = (
        db.execute(
            select(versions)
            .where(versions.c.reconciliation_id == row["id"])
            .order_by(versions.c.version)
        )
        .mappings()
        .all()
    )
    return ReconciliationOut.model_validate({**row, "versions": [dict(v) for v in history]})


def save_version(
    db: Connection, request: Request, actor: UUID, row: dict[str, Any], reason: str
) -> None:
    versions = table("fuel_reconciliation_versions", db)
    # Caller holds the reconciliation row lock; versions cannot collide on recompute.
    previous = db.execute(
        select(versions.c.version)
        .where(versions.c.reconciliation_id == row["id"])
        .order_by(versions.c.version.desc())
    ).first()
    version = previous[0] + 1 if previous else 1
    result = calculate(db, row)
    db.execute(
        versions.insert().values(
            reconciliation_id=row["id"],
            version=version,
            computed_by=actor,
            reason=reason,
            result_json=result,
        )
    )
    audit(
        db,
        request,
        actor,
        "RECOMPUTE" if previous else "CREATE",
        "fuel_reconciliation",
        row["id"],
        after={"version": version, "reason": reason, "result": result},
        reason=reason,
    )


@router.get("/reconciliations", response_model=list[ReconciliationOut])
def periods(user: Operator, db: Db, vehicle_id: UUID | None = None) -> list[ReconciliationOut]:
    entity = table("fuel_reconciliations", db)
    query = select(entity).order_by(entity.c.from_at.desc())
    if vehicle_id:
        query = query.where(entity.c.vehicle_id == vehicle_id)
    return [period_out(db, dict(row)) for row in db.execute(query).mappings()]


@router.post("/reconciliations", response_model=ReconciliationOut, status_code=201)
def period_create(
    data: ReconciliationInput, user: Operator, request: Request, db: Db
) -> ReconciliationOut:
    find_vehicle(db, data.vehicle_id)
    entity = table("fuel_reconciliations", db)
    row = dict(
        db.execute(
            entity.insert().values(**data.model_dump(), created_by=user.id).returning(entity)
        )
        .mappings()
        .one()
    )
    save_version(db, request, user.id, row, "Kỳ do điều phối nhập và xác nhận")
    return period_out(db, row)


@router.post("/reconciliations/{period_id}/recompute", response_model=ReconciliationOut)
def period_recompute(
    period_id: UUID, data: Recompute, user: Operator, request: Request, db: Db
) -> ReconciliationOut:
    row = record(db, "fuel_reconciliations", period_id, True)
    save_version(db, request, user.id, row, data.reason)
    return period_out(db, row)


@router.post("/reconciliations/{period_id}/finalize", response_model=ReconciliationOut)
def period_finalize(
    period_id: UUID, data: Recompute, user: Operator, request: Request, db: Db
) -> ReconciliationOut:
    row = record(db, "fuel_reconciliations", period_id, True)
    if row["status"] == "FINAL":
        return period_out(db, row)
    entity = table("fuel_reconciliations", db)
    try:
        final = dict(
            db.execute(
                entity.update()
                .where(entity.c.id == period_id)
                .values(status="FINAL")
                .returning(entity)
            )
            .mappings()
            .one()
        )
    except IntegrityError as exc:
        raise HTTPException(409, "Kỳ FINAL cùng xe không được chồng lấn thời gian") from exc
    # Refresh the summary at confirmation; older computed versions remain immutable.
    save_version(db, request, user.id, final, data.reason)
    audit(
        db,
        request,
        user.id,
        "FINALIZE",
        "fuel_reconciliation",
        period_id,
        encoded(row),
        {**encoded(final), "reason": data.reason},
        reason=data.reason,
    )
    return period_out(db, final)

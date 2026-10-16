"""Read-only ADMIN reporting. Historical attempts are never reconstructed from current orders."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, select
from sqlalchemy.engine import Connection

from app.auth import Admin, Db
from app.database import table
from app.operations_policy import LOCAL
from app.reporting_policy import attempt_evidence, attempt_totals
from app.reporting_schemas import (
    ReportAttempts,
    ReportFinancial,
    ReportFinancialSources,
    ReportPeriod,
    ReportSummary,
    ReportVehicleIntervals,
    ReportVehicles,
)
from app.reporting_telemetry import mapped_report
from app.traccar import Traccar

router = APIRouter(prefix="/api/v1/reports", tags=["reporting"])


def period(date_from: date, date_to: date, vehicle_id: UUID | None = None) -> ReportPeriod:
    if date_from > date_to or date_to == date.max:
        raise HTTPException(422, "Khoảng báo cáo không hợp lệ")
    return ReportPeriod(date_from=date_from, date_to=date_to, vehicle_id=vehicle_id)


Period = Annotated[ReportPeriod, Depends(period)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def bounds(value: ReportPeriod) -> tuple[datetime, datetime]:
    return (
        datetime.combine(value.date_from, time.min, LOCAL),
        datetime.combine(value.date_to + timedelta(days=1), time.min, LOCAL),
    )


def trip_query(db: Connection, value: ReportPeriod) -> Select[Any]:
    trips = table("trips", db)
    query = select(trips).where(
        trips.c.trip_date >= value.date_from, trips.c.trip_date <= value.date_to
    )
    if value.vehicle_id:
        query = query.where(trips.c.vehicle_id == value.vehicle_id)
    return query


def attempts_for(db: Connection, value: ReportPeriod) -> tuple[int, list[dict[str, Any]]]:
    trips, stops, deliveries = (table(n, db) for n in ("trips", "trip_stops", "deliveries"))
    selected = [dict(r) for r in db.execute(trip_query(db, value)).mappings()]
    if not selected:
        return 0, []
    rows = [
        dict(r)
        for r in db.execute(
            select(
                trips.c.id.label("trip_id"),
                trips.c.trip_date,
                trips.c.vehicle_id,
                trips.c.created_at.label("trip_created_at"),
                stops.c.id.label("attempt_id"),
                stops.c.delivery_id,
                stops.c.status.label("attempt_status"),
                stops.c.arrived_at,
                stops.c.completed_at,
                deliveries.c.code.label("delivery_code"),
            )
            .select_from(
                stops.join(trips, trips.c.id == stops.c.trip_id).join(
                    deliveries, deliveries.c.id == stops.c.delivery_id
                )
            )
            .where(trips.c.id.in_([r["id"] for r in selected]))
            .order_by(trips.c.trip_date, trips.c.id, stops.c.sequence_no)
        ).mappings()
    ]
    if not rows:
        return len(selected), []
    delivery_ids = {r["delivery_id"] for r in rows}
    chronology = list(
        db.execute(
            select(stops.c.id, stops.c.delivery_id, trips.c.created_at)
            .select_from(stops.join(trips, trips.c.id == stops.c.trip_id))
            .where(stops.c.delivery_id.in_(delivery_ids))
        ).mappings()
    )
    plans_t, events_t, audits_t = (
        table(n, db) for n in ("trip_route_plans", "delivery_status_events", "audit_logs")
    )
    plans = [
        dict(r)
        for r in db.execute(
            select(plans_t).where(
                plans_t.c.trip_id.in_([r["id"] for r in selected]),
                plans_t.c.approved_at.is_not(None),
            )
        ).mappings()
    ]
    events = [
        dict(r)
        for r in db.execute(
            select(events_t).where(events_t.c.delivery_id.in_(delivery_ids))
        ).mappings()
    ]
    audits = [
        dict(r)
        for r in db.execute(
            select(audits_t).where(
                audits_t.c.resource_type == "delivery",
                audits_t.c.resource_id.in_([str(v) for v in delivery_ids]),
                audits_t.c.action.in_(["STATUS", "AUTO_ARRIVED", "CORRECT_ARRIVED"]),
            )
        ).mappings()
    ]
    for row in rows:
        history = [h for h in chronology if h["delivery_id"] == row["delivery_id"]]
        same_time = [h for h in history if h["created_at"] == row["trip_created_at"]]
        row["ambiguous_attempt_history"] = len(same_time) != 1
        later = [h["created_at"] for h in history if h["created_at"] > row["trip_created_at"]]
        row["next_attempt_created_at"] = min(later) if later else None
    return len(selected), [attempt_evidence(r, plans, events, audits) for r in rows]


@router.get("/summary", response_model=ReportSummary)
def summary(user: Admin, db: Db, selected: Period) -> dict[str, Any]:
    trips, items = attempts_for(db, selected)
    return dict(period=selected, trips=trips, **attempt_totals(items))


@router.get("/attempts", response_model=ReportAttempts)
def attempts(
    user: Admin, db: Db, selected: Period, limit: Limit = 50, offset: Offset = 0
) -> dict[str, Any]:
    _, items = attempts_for(db, selected)
    return dict(
        period=selected,
        total=len(items),
        limit=limit,
        offset=offset,
        items=items[offset : offset + limit],
    )


def financial_sources(db: Connection, value: ReportPeriod) -> list[dict[str, Any]]:
    start, end = bounds(value)
    fuel, expenses, trips = (table(n, db) for n in ("fuel_entries", "expenses", "trips"))
    query = select(fuel).where(fuel.c.filled_at >= start, fuel.c.filled_at < end)
    if value.vehicle_id:
        query = query.where(fuel.c.vehicle_id == value.vehicle_id)
    sources = []
    for row in db.execute(query.order_by(fuel.c.filled_at, fuel.c.id)).mappings():
        sources.append(
            dict(
                source_table="fuel_entries",
                record_id=row["id"],
                vehicle_id=row["vehicle_id"],
                trip_id=row["trip_id"],
                business_date=row["filled_at"].astimezone(LOCAL).date(),
                business_at=row["filled_at"],
                category="FUEL",
                liters=row["liters"],
                amount=row["amount"],
                included=row["deleted_at"] is None,
                exclusion_reason="VOIDED" if row["deleted_at"] is not None else None,
            )
        )
    query = (
        select(expenses, trips.c.vehicle_id, trips.c.trip_date)
        .select_from(expenses.join(trips, trips.c.id == expenses.c.trip_id))
        .where(trips.c.trip_date >= value.date_from, trips.c.trip_date <= value.date_to)
    )
    if value.vehicle_id:
        query = query.where(trips.c.vehicle_id == value.vehicle_id)
    for row in db.execute(query.order_by(trips.c.trip_date, expenses.c.id)).mappings():
        sources.append(
            dict(
                source_table="expenses",
                record_id=row["id"],
                vehicle_id=row["vehicle_id"],
                trip_id=row["trip_id"],
                business_date=row["trip_date"],
                business_at=row["incurred_at"],
                category=row["type"],
                liters=None,
                amount=row["amount"],
                included=True,
                exclusion_reason=None,
            )
        )
    return sources


@router.get("/financial/sources", response_model=ReportFinancialSources)
def financial_source_list(
    user: Admin, db: Db, selected: Period, limit: Limit = 50, offset: Offset = 0
) -> dict[str, Any]:
    items = financial_sources(db, selected)
    return dict(
        period=selected,
        total=len(items),
        limit=limit,
        offset=offset,
        items=items[offset : offset + limit],
    )


@router.get("/financial", response_model=ReportFinancial)
def financial(user: Admin, db: Db, selected: Period) -> dict[str, Any]:
    rows = financial_sources(db, selected)
    fuel = [r for r in rows if r["source_table"] == "fuel_entries" and r["included"]]
    expenses = [r for r in rows if r["source_table"] == "expenses" and r["included"]]
    missing = sum(r["amount"] is None for r in fuel)
    categories: dict[str, Decimal] = {}
    for row in expenses:
        categories[row["category"]] = categories.get(row["category"], Decimal(0)) + row["amount"]
    reconciliations, excluded = current_reconciliations(db, selected)
    return dict(
        period=selected,
        fuel_entries=len(fuel),
        total_fuel_liters=sum((r["liters"] for r in fuel), Decimal(0)),
        total_fuel_cost=None if missing else sum((r["amount"] for r in fuel), Decimal(0)),
        fuel_missing_amount=missing,
        expenses=len(expenses),
        total_trip_expense=sum((r["amount"] for r in expenses), Decimal(0)),
        expense_by_type=categories,
        grand_total=None,
        grand_total_reason="chưa đủ quy tắc chống trùng",
        reconciliations=reconciliations,
        excluded_reconciliations=excluded,
    )


def current_reconciliations(
    db: Connection, value: ReportPeriod
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    start, end = bounds(value)
    periods, versions = (
        table(n, db) for n in ("fuel_reconciliations", "fuel_reconciliation_versions")
    )
    query = select(periods).where(periods.c.from_at < end, periods.c.to_at > start)
    if value.vehicle_id:
        query = query.where(periods.c.vehicle_id == value.vehicle_id)
    rows = list(db.execute(query.order_by(periods.c.from_at, periods.c.id)).mappings())
    history = (
        list(
            db.execute(
                select(versions)
                .where(versions.c.reconciliation_id.in_([r["id"] for r in rows]))
                .order_by(versions.c.version.desc())
            ).mappings()
        )
        if rows
        else []
    )
    included, excluded = [], []
    for row in rows:
        current = next((v for v in history if v["reconciliation_id"] == row["id"]), None)
        reason = (
            "NOT_FINAL"
            if row["status"] != "FINAL"
            else "NOT_WHOLLY_IN_REPORT_PERIOD"
            if row["from_at"] < start or row["to_at"] > end
            else "VERSION_MISSING"
            if current is None
            else None
        )
        if reason:
            excluded.append(dict(reconciliation_id=row["id"], reason=reason))
            continue
        assert current is not None
        result = current["result_json"]
        included.append(
            dict(
                reconciliation_id=row["id"],
                vehicle_id=row["vehicle_id"],
                from_at=row["from_at"],
                to_at=row["to_at"],
                version_id=current["id"],
                version=current["version"],
                computed_at=current["computed_at"],
                **{
                    k: result[k]
                    for k in (
                        "data_status",
                        "reasons",
                        "actual_liters",
                        "expected_liters",
                        "variance_pct",
                        "alert_flag",
                    )
                },
            )
        )
    return included, excluded


def vehicle_observations(db: Connection, value: ReportPeriod, vehicle_id: UUID) -> dict[str, Any]:
    start, end = bounds(value)
    logs = table("audit_logs", db)
    history = list(
        db.execute(
            select(logs)
            .where(
                logs.c.resource_type == "vehicle",
                logs.c.resource_id == str(vehicle_id),
                logs.c.action.in_(["CREATE", "UPDATE"]),
                logs.c.created_at < end,
            )
            .order_by(logs.c.created_at, logs.c.id)
        ).mappings()
    )
    return mapped_report(Traccar(), [dict(r) for r in history], start, end)


@router.get("/vehicles", response_model=ReportVehicles)
def vehicle_reports(
    user: Admin, db: Db, selected: Period, limit: Limit = 50, offset: Offset = 0
) -> dict[str, Any]:
    vehicles = table("vehicles", db)
    query = select(vehicles.c.id, vehicles.c.plate_no).order_by(vehicles.c.plate_no, vehicles.c.id)
    if selected.vehicle_id:
        query = query.where(vehicles.c.id == selected.vehicle_id)
    rows = list(db.execute(query).mappings())
    trips = list(db.execute(trip_query(db, selected)).mappings())
    stops = table("trip_stops", db)
    stop_trips: list[UUID] = (
        list(
            db.execute(
                select(stops.c.trip_id).where(stops.c.trip_id.in_([r["id"] for r in trips]))
            ).scalars()
        )
        if trips
        else []
    )
    items = []
    for row in rows[offset : offset + limit]:
        own = {t["id"] for t in trips if t["vehicle_id"] == row["id"]}
        result = vehicle_observations(db, selected, row["id"])
        result.pop("intervals")
        items.append(
            dict(
                vehicle_id=row["id"],
                plate_no=row["plate_no"],
                trips=len(own),
                attempts=sum(t in own for t in stop_trips),
                **result,
            )
        )
    return dict(period=selected, total=len(rows), limit=limit, offset=offset, items=items)


@router.get("/vehicles/{vehicle_id}/intervals", response_model=ReportVehicleIntervals)
def vehicle_intervals(
    vehicle_id: UUID,
    user: Admin,
    db: Db,
    selected: Period,
    limit: Limit = 50,
    offset: Offset = 0,
) -> dict[str, Any]:
    vehicles = table("vehicles", db)
    if selected.vehicle_id is not None and selected.vehicle_id != vehicle_id:
        raise HTTPException(422, "Bộ lọc xe không khớp")
    if db.scalar(select(vehicles.c.id).where(vehicles.c.id == vehicle_id)) is None:
        raise HTTPException(404, "Không tìm thấy xe")
    result = vehicle_observations(db, selected, vehicle_id)
    items = result["intervals"]
    return dict(
        period=selected,
        vehicle_id=vehicle_id,
        traccar_device_id=result["traccar_device_id"],
        traccar_device_ids=result["traccar_device_ids"],
        mapping_audit_ids=result["mapping_audit_ids"],
        reasons=result["reasons"],
        total=len(items),
        limit=limit,
        offset=offset,
        items=items[offset : offset + limit],
    )

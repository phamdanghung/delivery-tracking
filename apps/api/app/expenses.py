import hashlib
from typing import Any
from uuid import UUID, uuid5

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.engine import Connection

from app.auth import Db, User
from app.database import audit, table
from app.expense_schemas import ExpenseData, ExpenseInput, ExpenseOut
from app.fuel import encoded, record
from app.schemas import UserOut

router = APIRouter(prefix="/api/v1/expenses", tags=["expenses"])


def writable_trip(db: Connection, identifier: UUID, user: UserOut) -> dict[str, Any]:
    trip = record(db, "trips", identifier, True)
    if user.role == "DRIVER":
        profiles = table("driver_profiles", db)
        assigned = db.scalar(
            select(profiles.c.id).where(
                profiles.c.id == trip["driver_id"],
                profiles.c.user_id == user.id,
                profiles.c.active.is_(True),
            )
        )
        if assigned is None or trip["status"] not in ("ACTIVE", "COMPLETED"):
            raise HTTPException(
                409, "Chuyến đã thay đổi hoặc không còn thuộc phân công hợp lệ; xem trạng thái mới"
            )
    elif user.role != "DISPATCHER":
        raise HTTPException(403, "Chỉ điều phối hoặc tài xế được ghi chi phí chuyến")
    return trip


def expense_create(
    trip_id: UUID,
    data: ExpenseData,
    client_action_id: UUID,
    user: UserOut,
    request: Request,
    db: Connection,
) -> ExpenseOut:
    db.execute(text("SELECT pg_advisory_xact_lock(73210402)"))
    entity = table("expenses", db)
    digest = hashlib.sha256((str(trip_id) + data.model_dump_json()).encode()).hexdigest()
    old = (
        db.execute(
            select(entity).where(
                entity.c.created_by == user.id, entity.c.client_action_id == client_action_id
            )
        )
        .mappings()
        .first()
    )
    if old:
        if old["request_hash"] != digest:
            raise HTTPException(409, "client_action_id đã dùng cho chi phí khác")
        return ExpenseOut.model_validate(old)
    writable_trip(db, trip_id, user)
    values = data.model_dump(exclude={"receipt_metadata"})
    if data.receipt_metadata:
        metadata = data.receipt_metadata
        receipt_id = uuid5(user.id, "receipt:" + str(client_action_id))
        entity_receipts = table("expense_receipts", db)
        receipt = (
            db.execute(select(entity_receipts).where(entity_receipts.c.id == receipt_id))
            .mappings()
            .first()
        )
        if receipt is None:
            raise HTTPException(409, "Biên lai chưa được upload; giữ ảnh để đồng bộ")
        receipt_digest = hashlib.sha256(
            (metadata.content_type + metadata.model_dump_json()).encode()
        ).hexdigest()
        if (
            receipt["trip_id"] != trip_id
            or receipt["created_by"] != user.id
            or receipt["client_action_id"] != client_action_id
            or metadata.trip_id != trip_id
            or metadata.client_action_id != client_action_id
            or receipt["request_hash"] != receipt_digest
        ):
            raise HTTPException(409, "Biên lai phải thuộc đúng chuyến/người nhập/command hiện tại")
        values["receipt_id"] = receipt_id
    identifier = uuid5(user.id, "expense:" + str(client_action_id))
    row = (
        db.execute(
            entity.insert()
            .values(
                **values,
                id=identifier,
                trip_id=trip_id,
                client_action_id=client_action_id,
                request_hash=digest,
                created_by=user.id,
            )
            .returning(entity)
        )
        .mappings()
        .one()
    )
    result = ExpenseOut.model_validate(row)
    audit(db, request, user.id, "CREATE", "expense", result.id, after=encoded(result))
    return result


def scoped_expense(db: Connection, expense_id: UUID, user: UserOut) -> dict[str, Any]:
    entity = table("expenses", db)
    query = select(entity).where(entity.c.id == expense_id)
    if user.role == "DRIVER":
        query = query.where(entity.c.created_by == user.id)
    row = db.execute(query).mappings().first()
    if row is None:
        raise HTTPException(404, "Không tìm thấy chi phí trong phạm vi của bạn")
    return dict(row)


@router.get("", response_model=list[ExpenseOut])
def expense_list(user: User, db: Db, trip_id: UUID | None = None) -> list[dict[str, Any]]:
    entity = table("expenses", db)
    query = select(entity).order_by(entity.c.incurred_at.desc())
    if user.role == "DRIVER":
        query = query.where(entity.c.created_by == user.id)
    if trip_id:
        query = query.where(entity.c.trip_id == trip_id)
    return [dict(row) for row in db.execute(query).mappings()]


@router.post("", response_model=ExpenseOut, status_code=201)
def expense_post(data: ExpenseInput, user: User, request: Request, db: Db) -> ExpenseOut:
    value = ExpenseData.model_validate(data.model_dump(exclude={"trip_id", "client_action_id"}))
    return expense_create(data.trip_id, value, data.client_action_id, user, request, db)


@router.get("/{expense_id}", response_model=ExpenseOut)
def expense_get(expense_id: UUID, user: User, db: Db) -> dict[str, Any]:
    return scoped_expense(db, expense_id, user)

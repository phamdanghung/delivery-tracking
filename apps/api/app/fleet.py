from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.auth import Admin, Db, Operator, hasher
from app.database import audit, table
from app.schemas import DriverInput, Role, UserCreate, UserOut, UserUpdate, VehicleInput, VehicleOut
from app.traccar import Traccar

router = APIRouter(prefix="/api/v1", tags=["fleet"])


@router.get("/users", response_model=list[UserOut])
def users_list(user: Admin, db: Db) -> list[UserOut]:
    users = table("users", db)
    return [
        UserOut.model_validate(row)
        for row in db.execute(select(users).order_by(users.c.full_name)).mappings()
    ]


@router.post("/users", response_model=UserOut, status_code=201)
def user_create(data: UserCreate, user: Admin, request: Request, db: Db) -> UserOut:
    users = table("users", db)
    values = data.model_dump(exclude={"password"})
    values["password_hash"] = hasher.hash(data.password)
    try:
        row = db.execute(users.insert().values(**values).returning(users)).mappings().one()
    except IntegrityError as exc:
        raise HTTPException(409, "Email đã tồn tại") from exc
    result = UserOut.model_validate(row)
    audit(db, request, user.id, "CREATE", "user", result.id, after=result.model_dump(mode="json"))
    if result.role == Role.DRIVER:
        db.execute(table("driver_profiles", db).insert().values(user_id=result.id))
    return result


@router.patch("/users/{user_id}", response_model=UserOut)
def user_update(user_id: UUID, data: UserUpdate, user: Admin, request: Request, db: Db) -> UserOut:
    # Serialize admin mutations so concurrent requests cannot remove the last ADMIN.
    db.execute(text("SELECT pg_advisory_xact_lock(73210401)"))
    users = table("users", db)
    row = (
        db.execute(select(users).where(users.c.id == user_id).with_for_update()).mappings().first()
    )
    if row is None:
        raise HTTPException(404, "Không tìm thấy người dùng")
    before = UserOut.model_validate(row)
    values = data.model_dump(exclude_unset=True, exclude={"password"})
    if any(values.get(key, row[key]) is None for key in ("role", "full_name", "is_active")):
        raise HTTPException(422, "Tên, vai trò và trạng thái không được rỗng")
    losing_admin = (
        before.role == Role.ADMIN
        and before.is_active
        and (values.get("role", before.role) != Role.ADMIN or values.get("is_active") is False)
    )
    if (
        losing_admin
        and db.scalar(
            select(func.count())
            .select_from(users)
            .where(users.c.role == Role.ADMIN, users.c.is_active.is_(True))
        )
        == 1
    ):
        raise HTTPException(409, "Phải giữ ít nhất một ADMIN hoạt động")
    profiles = table("driver_profiles", db)
    if before.role == Role.DRIVER and values.get("role", Role.DRIVER) != Role.DRIVER:
        raise HTTPException(
            409, "Không đổi vai trò user đã liên kết driver profile; hãy vô hiệu hóa tài khoản"
        )
    if data.password is not None:
        values["password_hash"] = hasher.hash(data.password)
    values["updated_at"] = datetime.now(UTC)
    found = (
        db.execute(users.update().where(users.c.id == user_id).values(**values).returning(users))
        .mappings()
        .one()
    )
    result = UserOut.model_validate(found)
    if before.role != Role.DRIVER and result.role == Role.DRIVER:
        db.execute(profiles.insert().values(user_id=user_id))
    # Active/role changes and password resets invalidate existing sessions immediately.
    if any(key in data.model_fields_set for key in ("password", "role", "is_active")):
        sessions = table("auth_sessions", db)
        db.execute(
            sessions.update()
            .where(sessions.c.user_id == user_id)
            .values(revoked_at=datetime.now(UTC))
        )
    audit(
        db,
        request,
        user.id,
        "UPDATE",
        "user",
        user_id,
        before.model_dump(mode="json"),
        result.model_dump(mode="json"),
    )
    return result


@router.get("/vehicles", response_model=list[VehicleOut])
def vehicles_list(user: Operator, db: Db) -> list[VehicleOut]:
    vehicles = table("vehicles", db)
    return [
        VehicleOut.model_validate(row)
        for row in db.execute(select(vehicles).order_by(vehicles.c.plate_no)).mappings()
    ]


def validate_mapping(device_id: int | None) -> None:
    if device_id is not None and not Traccar().device_exists(device_id):
        raise HTTPException(
            422, "Thiết bị Traccar không tồn tại hoặc adapter không có quyền truy cập"
        )


@router.get("/gps/devices")
def device_list(user: Admin) -> list[dict[str, Any]]:
    return [
        {key: item.get(key) for key in ("id", "name", "uniqueId", "status")}
        for item in Traccar().get("devices")
    ]


@router.post("/vehicles", response_model=VehicleOut, status_code=201)
def vehicle_create(data: VehicleInput, user: Admin, request: Request, db: Db) -> VehicleOut:
    validate_mapping(data.traccar_device_id)
    vehicles = table("vehicles", db)
    try:
        row = (
            db.execute(vehicles.insert().values(**data.model_dump()).returning(vehicles))
            .mappings()
            .one()
        )
    except IntegrityError as exc:
        raise HTTPException(409, "Biển số hoặc thiết bị đã được sử dụng") from exc
    result = VehicleOut.model_validate(row)
    audit(
        db, request, user.id, "CREATE", "vehicle", result.id, after=result.model_dump(mode="json")
    )
    return result


@router.put("/vehicles/{vehicle_id}", response_model=VehicleOut)
def vehicle_update(
    vehicle_id: UUID, data: VehicleInput, user: Admin, request: Request, db: Db
) -> VehicleOut:
    vehicles = table("vehicles", db)
    old = (
        db.execute(select(vehicles).where(vehicles.c.id == vehicle_id).with_for_update())
        .mappings()
        .first()
    )
    if old is None:
        raise HTTPException(404, "Không tìm thấy xe")
    validate_mapping(data.traccar_device_id)
    try:
        row = (
            db.execute(
                vehicles.update()
                .where(vehicles.c.id == vehicle_id)
                .values(**data.model_dump())
                .returning(vehicles)
            )
            .mappings()
            .one()
        )
    except IntegrityError as exc:
        raise HTTPException(409, "Biển số hoặc thiết bị đã được sử dụng") from exc
    if old["traccar_device_id"] != data.traccar_device_id:
        # Old-device locations must never be shown under a newly mapped device.
        snapshots = table("gps_snapshots", db)
        db.execute(snapshots.delete().where(snapshots.c.vehicle_id == vehicle_id))
        events = table("vehicle_state_events", db)
        db.execute(
            events.update()
            .where(events.c.vehicle_id == vehicle_id, events.c.ended_at.is_(None))
            .values(ended_at=datetime.now(UTC))
        )
    result = VehicleOut.model_validate(row)
    audit(
        db,
        request,
        user.id,
        "UPDATE",
        "vehicle",
        vehicle_id,
        VehicleOut.model_validate(old).model_dump(mode="json"),
        result.model_dump(mode="json"),
    )
    return result


@router.delete("/vehicles/{vehicle_id}", status_code=204)
def vehicle_delete(vehicle_id: UUID, user: Admin, request: Request, db: Db) -> None:
    vehicles = table("vehicles", db)
    row = (
        db.execute(select(vehicles).where(vehicles.c.id == vehicle_id).with_for_update())
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Không tìm thấy xe")
    before = VehicleOut.model_validate(row).model_dump(mode="json")
    try:
        db.execute(vehicles.delete().where(vehicles.c.id == vehicle_id))
    except IntegrityError as exc:
        raise HTTPException(
            409, "Xe đã có dữ liệu vận hành; hãy cập nhật trạng thái thay vì xóa"
        ) from exc
    audit(db, request, user.id, "DELETE", "vehicle", vehicle_id, before=before)


@router.get("/drivers")
def drivers_list(user: Operator, db: Db) -> list[dict[str, Any]]:
    profiles, users = table("driver_profiles", db), table("users", db)
    rows = db.execute(
        select(profiles, users.c.full_name, users.c.phone, users.c.is_active).join(
            users, profiles.c.user_id == users.c.id
        )
    ).mappings()
    result = [dict(row) for row in rows]
    trips, vehicles = table("trips", db), table("vehicles", db)
    assignments = (
        db.execute(
            select(
                trips.c.id.label("trip_id"),
                trips.c.driver_id,
                trips.c.vehicle_id,
                trips.c.trip_date,
                trips.c.status,
                vehicles.c.plate_no,
            )
            .join(vehicles, trips.c.vehicle_id == vehicles.c.id)
            .order_by(trips.c.trip_date.desc())
        )
        .mappings()
        .all()
    )
    for profile in result:
        profile["vehicle_assignments"] = [
            {key: value for key, value in assignment.items() if key != "driver_id"}
            for assignment in assignments
            if assignment["driver_id"] == profile["id"]
        ]
    return result


@router.put("/drivers/{driver_id}")
def driver_update(
    driver_id: UUID, data: DriverInput, user: Admin, request: Request, db: Db
) -> dict[str, Any]:
    profiles, users = table("driver_profiles", db), table("users", db)
    old = db.execute(select(profiles).where(profiles.c.id == driver_id)).mappings().first()
    if old is None:
        raise HTTPException(404, "Không tìm thấy hồ sơ tài xế")
    if old["user_id"] != data.user_id:
        raise HTTPException(422, "Không thay user của hồ sơ đã tạo; dùng hồ sơ đúng user")
    if db.scalar(select(users.c.role).where(users.c.id == data.user_id)) != Role.DRIVER:
        raise HTTPException(422, "Hồ sơ phải liên kết user DRIVER")
    result = dict(
        db.execute(
            profiles.update()
            .where(profiles.c.id == driver_id)
            .values(active=data.active)
            .returning(profiles)
        )
        .mappings()
        .one()
    )
    audit(
        db,
        request,
        user.id,
        "UPDATE",
        "driver_profile",
        driver_id,
        {"active": old["active"], "user_id": str(old["user_id"])},
        {"active": result["active"], "user_id": str(result["user_id"])},
    )
    return result

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.auth import Db, Operator, User
from app.config import get_settings
from app.database import audit
from app.delivery_schemas import (
    Commitment,
    DeliveryDetailOut,
    DeliveryInput,
    DeliveryOut,
    Point,
    RescheduleInput,
    RescheduleOut,
    StatusCommand,
    TripConfigOut,
    TripInput,
    TripOut,
)
from app.schemas import UserOut

router = APIRouter(prefix="/api/v1", tags=["delivery-trip"])
LOCAL = ZoneInfo("Asia/Bangkok")
TRANSITIONS = {
    "ASSIGNED": {"EN_ROUTE", "CANCELLED"},
    "EN_ROUTE": {"ARRIVED"},
    "ARRIVED": {"DELIVERING", "FAILED"},
    "DELIVERING": {"DELIVERED", "FAILED"},
    "CREATED": {"CANCELLED"},
    "PLANNED": {"CANCELLED"},
}
DELIVERY_SELECT = """SELECT d.*, ST_Y(d.location::geometry) AS latitude,
 ST_X(d.location::geometry) AS longitude, a.trip_id, a.vehicle_id, a.driver_id,
 a.plate_no, a.driver_name, a.eta_at, a.trip_status FROM deliveries d LEFT JOIN LATERAL (
 SELECT t.id AS trip_id,t.vehicle_id,t.driver_id,v.plate_no,u.full_name AS driver_name,s.eta_at
 ,t.status AS trip_status
 FROM trip_stops s JOIN trips t ON t.id=s.trip_id
 LEFT JOIN vehicles v ON v.id=t.vehicle_id
 LEFT JOIN driver_profiles p ON p.id=t.driver_id LEFT JOIN users u ON u.id=p.user_id
 WHERE s.delivery_id=d.id ORDER BY t.created_at DESC,t.id DESC LIMIT 1
) a ON true"""


def delivery(db: Connection, identifier: UUID, user: UserOut) -> DeliveryOut:
    row = (
        db.execute(text(DELIVERY_SELECT + " WHERE d.id=:id"), {"id": identifier}).mappings().first()
    )
    if row is None:
        raise HTTPException(404, "Không tìm thấy đơn giao")
    if user.role == "DRIVER" and not db.scalar(
        text("""SELECT EXISTS(SELECT 1
        FROM driver_profiles WHERE id=:driver AND user_id=:user AND active)"""),
        {"driver": row["driver_id"], "user": user.id},
    ):
        raise HTTPException(403, "Chỉ được truy cập đơn thuộc chuyến của mình")
    if user.role == "DRIVER" and row["trip_status"] not in {"PLANNED", "ACTIVE", "COMPLETED"}:
        raise HTTPException(403, "Chuyến nháp chưa được duyệt/xuất cho tài xế")
    return DeliveryOut.model_validate(row)


def lock_delivery(db: Connection, identifier: UUID, user: UserOut) -> DeliveryOut:
    # Same order for trip/status/reschedule mutations prevents double assignment and stale writes.
    db.execute(text("SELECT pg_advisory_xact_lock(73210402)"))
    db.execute(text("SELECT id FROM deliveries WHERE id=:id FOR UPDATE"), {"id": identifier})
    return delivery(db, identifier, user)


def event(
    db: Connection,
    request: Request,
    user: UserOut,
    identifier: UUID,
    old: str | None,
    new: str,
    reason: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> None:
    db.execute(
        text("""INSERT INTO delivery_status_events
        (delivery_id,from_status,to_status,actor_user_id,source,reason,request_id,location)
        VALUES (:id,CAST(:old AS delivery_status),CAST(:new AS delivery_status),:actor,
        :source,:reason,:request,CASE WHEN CAST(:lat AS double precision) IS NULL THEN NULL ELSE
        ST_SetSRID(ST_MakePoint(:lon,:lat),4326)::geography END)"""),
        {
            "id": identifier,
            "old": old,
            "new": new,
            "actor": user.id,
            "source": "DRIVER" if user.role == "DRIVER" else "DISPATCH",
            "reason": reason,
            "request": request.state.request_id,
            "lat": latitude,
            "lon": longitude,
        },
    )
    db.execute(
        text("""UPDATE deliveries SET status=CAST(:new AS delivery_status),
        updated_at=now() WHERE id=:id"""),
        {"new": new, "id": identifier},
    )


def public(value: Any) -> Any:
    return jsonable_encoder(value)


@router.post("/deliveries", response_model=DeliveryOut, status_code=201)
def create_delivery(data: DeliveryInput, user: Operator, request: Request, db: Db) -> DeliveryOut:
    identifier = uuid4()
    values = data.model_dump()
    values.update(id=identifier, code="DH-" + identifier.hex.upper(), actor=user.id)
    db.execute(
        text("""INSERT INTO deliveries
        (id,code,recipient_name,recipient_phone,address_text,location,commitment_type,
        appointment_at,window_start,window_end,deadline_at,scheduled_date,weight_kg,volume_m3,
        notes,created_by) VALUES (:id,:code,:recipient_name,:recipient_phone,:address_text,
        CASE WHEN CAST(:latitude AS double precision) IS NULL THEN NULL ELSE
        ST_SetSRID(ST_MakePoint(:longitude,:latitude),4326)::geography END,
        CAST(:commitment_type AS commitment_type),:appointment_at,:window_start,:window_end,
        :deadline_at,:scheduled_date,:weight_kg,:volume_m3,:notes,:actor)"""),
        values,
    )
    event(db, request, user, identifier, None, "CREATED")
    result = delivery(db, identifier, user)
    audit(db, request, user.id, "CREATE", "delivery", identifier, after=public(result))
    return result


@router.get("/deliveries", response_model=list[DeliveryOut])
def list_deliveries(
    user: Operator,
    db: Db,
    scheduled_date: date | None = None,
    status: str | None = None,
    search: str = Query(default="", max_length=200),
    vehicle_id: UUID | None = None,
    driver_id: UUID | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[DeliveryOut]:
    rows = db.execute(
        text(
            DELIVERY_SELECT
            + """ WHERE
        (CAST(:date AS date) IS NULL OR d.scheduled_date=:date)
        AND (CAST(:status AS text) IS NULL OR d.status::text=:status)
        AND (CAST(:vehicle AS uuid) IS NULL OR a.vehicle_id=:vehicle)
        AND (CAST(:driver AS uuid) IS NULL OR a.driver_id=:driver)
        AND (:q='' OR strpos(lower(d.code||' '||d.recipient_name||' '||d.recipient_phone),
                             lower(:q))>0)
        ORDER BY d.created_at DESC,d.id LIMIT :limit OFFSET :offset"""
        ),
        {
            "date": scheduled_date,
            "status": status,
            "vehicle": vehicle_id,
            "driver": driver_id,
            "q": search,
            "limit": limit,
            "offset": offset,
        },
    ).mappings()
    return [DeliveryOut.model_validate(row) for row in rows]


@router.get("/deliveries/{delivery_id}", response_model=DeliveryDetailOut)
def detail_delivery(delivery_id: UUID, user: User, db: Db) -> dict[str, Any]:
    result = delivery(db, delivery_id, user)
    events = db.execute(
        text("""SELECT e.id,e.from_status,e.to_status,e.event_time,e.source,
        e.reason,e.actor_user_id,u.full_name AS actor_name,e.request_id,
        ST_Y(e.location::geometry) AS latitude,ST_X(e.location::geometry) AS longitude
        FROM delivery_status_events e LEFT JOIN users u ON u.id=e.actor_user_id
        WHERE delivery_id=:id ORDER BY event_time,id"""),
        {"id": delivery_id},
    ).mappings()
    proposals = db.execute(
        text("""SELECT p.*,u.full_name AS proposer_name
        FROM delivery_reschedule_proposals p JOIN users u ON u.id=p.proposed_by
        WHERE delivery_id=:id ORDER BY created_at,id"""),
        {"id": delivery_id},
    ).mappings()
    audits = db.execute(
        text("""SELECT action,before_json,after_json,reason,created_at,actor_user_id,
        request_id FROM audit_logs WHERE resource_type='delivery' AND resource_id=:id
        ORDER BY created_at,id"""),
        {"id": str(delivery_id)},
    ).mappings()
    return {
        "delivery": result,
        "events": [dict(x) for x in events],
        "reschedule_proposals": [dict(x) for x in proposals],
        "audit": [dict(x) for x in audits],
    }


@router.put("/deliveries/{delivery_id}", response_model=DeliveryOut)
def edit_delivery(
    delivery_id: UUID, data: DeliveryInput, user: Operator, request: Request, db: Db
) -> DeliveryOut:
    before = lock_delivery(db, delivery_id, user)
    if before.status not in {"CREATED", "RESCHEDULED"}:
        raise HTTPException(409, "Chỉ sửa đơn trước khi lập chuyến")
    values = data.model_dump()
    values["id"] = delivery_id
    db.execute(
        text("""UPDATE deliveries SET recipient_name=:recipient_name,
        recipient_phone=:recipient_phone,address_text=:address_text,
        location=CASE WHEN CAST(:latitude AS double precision) IS NULL THEN NULL ELSE
        ST_SetSRID(ST_MakePoint(:longitude,:latitude),4326)::geography END,
        commitment_type=CAST(:commitment_type AS commitment_type),appointment_at=:appointment_at,
        window_start=:window_start,window_end=:window_end,deadline_at=:deadline_at,
        scheduled_date=:scheduled_date,weight_kg=:weight_kg,volume_m3=:volume_m3,notes=:notes,
        updated_at=now() WHERE id=:id"""),
        values,
    )
    result = delivery(db, delivery_id, user)
    audit(db, request, user.id, "UPDATE", "delivery", delivery_id, public(before), public(result))
    return result


def uploaded_pod(db: Connection, delivery_id: UUID) -> bool:
    # Metadata alone is insufficient: a private object must actually exist (M5 upload deferred).
    import boto3
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError

    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key.get_secret_value(),
        aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
        config=Config(connect_timeout=5, read_timeout=5, retries={"max_attempts": 1}),
    )
    rows = db.execute(
        text("""SELECT object_key,sha256 FROM pod_photos
        WHERE delivery_id=:id AND uploaded_at IS NOT NULL AND sha256 IS NOT NULL"""),
        {"id": delivery_id},
    ).mappings()
    try:
        for row in rows:
            try:
                info = client.head_object(Bucket=settings.s3_bucket, Key=row["object_key"])
                if info.get("ContentLength", 0) > 0:
                    return True
            except ClientError as exc:
                if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                    continue
                raise HTTPException(503, "Chưa xác minh được ảnh trong storage") from exc
            except BotoCoreError as exc:
                raise HTTPException(503, "Storage không phản hồi") from exc
        return False
    finally:
        client.close()


@router.post("/deliveries/{delivery_id}/status", response_model=DeliveryOut)
def change_status(
    delivery_id: UUID, data: StatusCommand, user: User, request: Request, db: Db
) -> DeliveryOut:
    before = lock_delivery(db, delivery_id, user)
    if data.from_status != before.status:
        raise HTTPException(409, "Trạng thái đã thay đổi; tải lại đơn")
    if user.role == "DRIVER" and data.to_status == "CANCELLED":
        raise HTTPException(403, "Tài xế không được hủy đơn")
    if data.to_status not in TRANSITIONS.get(before.status, set()):
        raise HTTPException(409, "Chuyển trạng thái không hợp lệ hoặc chưa mở trong M2")
    if data.to_status in {"FAILED", "CANCELLED"} and not data.reason:
        raise HTTPException(422, "Bắt buộc nhập lý do")
    if data.to_status != "CANCELLED":
        trip = db.execute(
            text("SELECT status FROM trips WHERE id=:id"), {"id": before.trip_id}
        ).scalar()
        if trip != "ACTIVE":
            raise HTTPException(409, "Chuyến chưa được duyệt/bắt đầu")
    if data.to_status == "DELIVERED" and not uploaded_pod(db, delivery_id):
        raise HTTPException(409, "Cần ít nhất một ảnh POD đã upload hợp lệ; upload thuộc M5")
    event(
        db,
        request,
        user,
        delivery_id,
        before.status,
        data.to_status,
        data.reason,
        data.latitude,
        data.longitude,
    )
    db.execute(
        text("""UPDATE trip_stops SET status=CAST(:status AS delivery_status),
        arrived_at=CASE WHEN :status='ARRIVED' THEN now() ELSE arrived_at END,
        completed_at=CASE WHEN :status IN ('DELIVERED','FAILED','CANCELLED') THEN now()
                          ELSE completed_at END WHERE delivery_id=:id AND trip_id=:trip
        AND status NOT IN ('DELIVERED','FAILED','CANCELLED')"""),
        {"status": data.to_status, "id": delivery_id, "trip": before.trip_id},
    )
    result = delivery(db, delivery_id, user)
    audit(
        db,
        request,
        user.id,
        "STATUS",
        "delivery",
        delivery_id,
        public(before),
        {"delivery": public(result), "reason": data.reason},
    )
    db.execute(
        text("""UPDATE audit_logs SET reason=:reason WHERE request_id=:request
        AND resource_type='delivery' AND resource_id=:id AND action='STATUS'"""),
        {"reason": data.reason, "request": request.state.request_id, "id": str(delivery_id)},
    )
    return result


def future_commitment(data: Commitment) -> None:
    start = data.appointment_at or data.window_start or data.deadline_at
    if (
        start is None
        or start <= datetime.now(UTC)
        or data.scheduled_date < datetime.now(LOCAL).date()
    ):
        raise HTTPException(422, "Lịch giao lại không được ở quá khứ")


@router.post("/deliveries/{delivery_id}/reschedule", response_model=RescheduleOut)
def reschedule(
    delivery_id: UUID, data: RescheduleInput, user: User, request: Request, db: Db
) -> dict[str, Any]:
    before = lock_delivery(db, delivery_id, user)
    if before.status != "FAILED":
        raise HTTPException(409, "Chỉ hẹn giao lại đơn FAILED")
    failure = db.scalar(
        text("""SELECT id FROM delivery_status_events WHERE delivery_id=:id
        AND to_status='FAILED' ORDER BY event_time DESC,id DESC LIMIT 1"""),
        {"id": delivery_id},
    )
    if failure is None:
        raise HTTPException(409, "Thiếu lịch sử thất bại hợp lệ")
    proposal = None
    commitment = data.commitment
    if data.proposal_id:
        if user.role == "DRIVER":
            raise HTTPException(403, "Tài xế chỉ đề xuất; điều phối mới xác nhận")
        proposal = (
            db.execute(
                text("""SELECT * FROM delivery_reschedule_proposals
            WHERE id=:proposal AND delivery_id=:id AND failure_event_id=:failure
            AND confirmed_at IS NULL FOR UPDATE"""),
                {"proposal": data.proposal_id, "id": delivery_id, "failure": failure},
            )
            .mappings()
            .first()
        )
        if proposal is None:
            raise HTTPException(409, "Đề xuất đã xác nhận hoặc không thuộc lần thất bại này")
        commitment = Commitment.model_validate(
            {key: proposal[key] for key in Commitment.model_fields}
        )
    assert commitment is not None
    future_commitment(commitment)
    values = commitment.model_dump()
    if user.role == "DRIVER":
        identifier = uuid4()
        db.execute(
            text("""INSERT INTO delivery_reschedule_proposals
            (id,delivery_id,failure_event_id,proposed_by,commitment_type,scheduled_date,
            appointment_at,window_start,window_end,deadline_at)
            VALUES (:id,:delivery,:failure,:actor,CAST(:commitment_type AS commitment_type),
            :scheduled_date,:appointment_at,:window_start,:window_end,:deadline_at)"""),
            {
                **values,
                "id": identifier,
                "delivery": delivery_id,
                "failure": failure,
                "actor": user.id,
            },
        )
        audit(
            db,
            request,
            user.id,
            "PROPOSE_RESCHEDULE",
            "delivery",
            delivery_id,
            after=public({"proposal_id": identifier, **values}),
        )
        return {"proposal_id": identifier, "confirmed": False, "delivery": before}
    db.execute(
        text("""UPDATE deliveries SET commitment_type=CAST(:commitment_type AS commitment_type),
        scheduled_date=:scheduled_date,appointment_at=:appointment_at,window_start=:window_start,
        window_end=:window_end,deadline_at=:deadline_at WHERE id=:id"""),
        {**values, "id": delivery_id},
    )
    if proposal:
        db.execute(
            text("""UPDATE delivery_reschedule_proposals SET confirmed_by=:actor,
            confirmed_at=now() WHERE id=:id"""),
            {"actor": user.id, "id": data.proposal_id},
        )
    event(
        db, request, user, delivery_id, "FAILED", "RESCHEDULED", "Điều phối xác nhận lịch giao lại"
    )
    result = delivery(db, delivery_id, user)
    audit(
        db, request, user.id, "RESCHEDULE", "delivery", delivery_id, public(before), public(result)
    )
    return {"confirmed": True, "delivery": result, "proposal_id": data.proposal_id}


@router.get("/trips/config", response_model=TripConfigOut)
def trip_config(user: Operator) -> dict[str, Any]:
    settings = get_settings()
    point = None
    if settings.company_latitude is not None and settings.company_longitude is not None:
        point = Point(latitude=settings.company_latitude, longitude=settings.company_longitude)
    return {
        "company": point,
        "configured": point is not None,
        "message": None if point else "Thiếu tọa độ công ty/xưởng trong cấu hình",
    }


def trip_detail(db: Connection, identifier: UUID, user: UserOut) -> TripOut:
    row = (
        db.execute(
            text("""SELECT t.*,v.plate_no,u.full_name AS driver_name,p.user_id,
        ST_Y(t.start_location::geometry) AS start_lat,ST_X(t.start_location::geometry) AS start_lon,
        ST_Y(t.end_location::geometry) AS end_lat,ST_X(t.end_location::geometry) AS end_lon,
        v.max_weight_kg,v.max_volume_m3 FROM trips t JOIN vehicles v ON v.id=t.vehicle_id
        JOIN driver_profiles p ON p.id=t.driver_id JOIN users u ON u.id=p.user_id
        WHERE t.id=:id"""),
            {"id": identifier},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Không tìm thấy chuyến")
    if user.role == "DRIVER" and (
        row["user_id"] != user.id or row["status"] not in {"PLANNED", "ACTIVE", "COMPLETED"}
    ):
        raise HTTPException(403, "Chỉ được truy cập chuyến của mình")
    stops = [
        dict(x)
        for x in db.execute(
            text("""SELECT s.*,d.code,d.recipient_name,
        d.recipient_phone,d.address_text,d.commitment_type,d.appointment_at,d.window_start,
        d.window_end,d.deadline_at,d.weight_kg,d.volume_m3 FROM trip_stops s
        JOIN deliveries d ON d.id=s.delivery_id WHERE trip_id=:id ORDER BY sequence_no"""),
            {"id": identifier},
        ).mappings()
    ]
    weight = sum(float(x["weight_kg"] or 0) for x in stops)
    volume = sum(float(x["volume_m3"] or 0) for x in stops)
    warnings = []
    if row["max_weight_kg"] is not None and weight > float(row["max_weight_kg"]):
        warnings.append("Vượt tải trọng xe; cảnh báo không khóa lưu chuyến")
    if row["max_volume_m3"] is not None and volume > float(row["max_volume_m3"]):
        warnings.append("Vượt thể tích xe; cảnh báo không khóa lưu chuyến")
    if any(x["weight_kg"] is None or x["volume_m3"] is None for x in stops):
        warnings.append("Có đơn chưa có kg/m³; tổng chỉ tính dữ liệu đã nhập")
    return TripOut(
        id=row["id"],
        trip_date=row["trip_date"],
        vehicle_id=row["vehicle_id"],
        driver_id=row["driver_id"],
        plate_no=row["plate_no"],
        driver_name=row["driver_name"],
        status=row["status"],
        start=Point(latitude=row["start_lat"], longitude=row["start_lon"])
        if row["start_lat"] is not None
        else None,
        end=Point(latitude=row["end_lat"], longitude=row["end_lon"])
        if row["end_lat"] is not None
        else None,
        weight_kg=weight,
        volume_m3=volume,
        warnings=warnings,
        stops=public(stops),
    )


@router.get("/trips", response_model=list[TripOut])
def list_trips(user: User, db: Db, trip_date: date | None = None) -> list[TripOut]:
    ids: Any = db.execute(
        text("""SELECT t.id FROM trips t JOIN driver_profiles p ON p.id=t.driver_id
        WHERE (CAST(:date AS date) IS NULL OR trip_date=:date)
        AND (:driver=false OR p.user_id=:user)
        AND (:driver=false OR t.status IN ('PLANNED','ACTIVE','COMPLETED'))
        ORDER BY created_at DESC,t.id LIMIT 200"""),
        {"date": trip_date, "driver": user.role == "DRIVER", "user": user.id},
    ).scalars()
    return [trip_detail(db, x, user) for x in ids]


@router.get("/trips/{trip_id}", response_model=TripOut)
def get_trip(trip_id: UUID, user: User, db: Db) -> TripOut:
    return trip_detail(db, trip_id, user)


@router.post("/trips", response_model=TripOut, status_code=201)
def create_trip(data: TripInput, user: Operator, request: Request, db: Db) -> TripOut:
    db.execute(text("SELECT pg_advisory_xact_lock(73210402)"))
    company = trip_config(user)["company"]
    start, end = data.start or company, data.end or company
    if start is None or end is None:
        raise HTTPException(422, "Thiếu cấu hình tọa độ công ty/xưởng hoặc điểm đầu/cuối thay thế")
    if not db.scalar(
        text("SELECT EXISTS(SELECT 1 FROM vehicles WHERE id=:id AND status='ACTIVE')"),
        {"id": data.vehicle_id},
    ):
        raise HTTPException(422, "Xe không hoạt động hoặc không tồn tại")
    if not db.scalar(
        text("""SELECT EXISTS(SELECT 1 FROM driver_profiles p JOIN users u
        ON u.id=p.user_id WHERE p.id=:id AND p.active AND u.is_active AND u.role='DRIVER')"""),
        {"id": data.driver_id},
    ):
        raise HTTPException(422, "Tài xế không hoạt động hoặc không tồn tại")
    selected = []
    for identifier in sorted(data.delivery_ids):
        row = lock_delivery(db, identifier, user)
        if row.status not in {"CREATED", "RESCHEDULED"} or row.scheduled_date != data.trip_date:
            raise HTTPException(409, "Đơn đã lập chuyến hoặc không thuộc ngày đã chọn")
        if row.latitude is None or row.longitude is None:
            raise HTTPException(422, "Đơn thiếu tọa độ; cần xác minh trước khi lập chuyến")
        selected.append(row)
    identifier = uuid4()
    db.execute(
        text("""INSERT INTO trips (id,trip_date,vehicle_id,driver_id,start_location,
        end_location,created_by) VALUES (:id,:date,:vehicle,:driver,
        ST_SetSRID(ST_MakePoint(:slon,:slat),4326)::geography,
        ST_SetSRID(ST_MakePoint(:elon,:elat),4326)::geography,:actor)"""),
        {
            "id": identifier,
            "date": data.trip_date,
            "vehicle": data.vehicle_id,
            "driver": data.driver_id,
            "slat": start.latitude,
            "slon": start.longitude,
            "elat": end.latitude,
            "elon": end.longitude,
            "actor": user.id,
        },
    )
    for sequence, item_id in enumerate(data.delivery_ids, 1):
        row = next(item for item in selected if item.id == item_id)
        db.execute(
            text("""INSERT INTO trip_stops (trip_id,delivery_id,sequence_no,status)
            VALUES (:trip,:delivery,:sequence,'PLANNED')"""),
            {"trip": identifier, "delivery": item_id, "sequence": sequence},
        )
        event(db, request, user, item_id, row.status, "PLANNED", "Đưa vào chuyến nháp")
        audit(
            db,
            request,
            user.id,
            "PLAN",
            "delivery",
            item_id,
            public(row),
            public(delivery(db, item_id, user)),
        )
    result = trip_detail(db, identifier, user)
    audit(db, request, user.id, "CREATE_DRAFT", "trip", identifier, after=public(result))
    return result


@router.post("/trips/{trip_id}/start", response_model=TripOut)
def start_trip(trip_id: UUID, user: User, request: Request, db: Db) -> TripOut:
    db.execute(text("SELECT pg_advisory_xact_lock(73210402)"))
    before = trip_detail(db, trip_id, user)
    if before.status != "PLANNED":
        raise HTTPException(409, "Chỉ bắt đầu chuyến đã duyệt sau tối ưu tuyến")
    rows = [delivery(db, UUID(str(x["delivery_id"])), user) for x in before.stops]
    if not rows or any(x.status != "ASSIGNED" for x in rows):
        raise HTTPException(409, "Các đơn phải đã được phân sau duyệt")
    if not db.scalar(
        text("""SELECT EXISTS(SELECT 1 FROM vehicles v,driver_profiles p,users u
        WHERE v.id=:vehicle AND v.status='ACTIVE' AND p.id=:driver AND p.active
        AND u.id=p.user_id AND u.is_active AND u.role='DRIVER')"""),
        {"vehicle": before.vehicle_id, "driver": before.driver_id},
    ):
        raise HTTPException(409, "Xe/tài xế không còn hoạt động")
    db.execute(text("UPDATE trips SET status='ACTIVE' WHERE id=:id"), {"id": trip_id})
    for row in rows:
        event(db, request, user, row.id, "ASSIGNED", "EN_ROUTE", "Bắt đầu chuyến đã duyệt")
        db.execute(
            text("UPDATE trip_stops SET status='EN_ROUTE' WHERE trip_id=:trip AND delivery_id=:id"),
            {"trip": trip_id, "id": row.id},
        )
        audit(
            db,
            request,
            user.id,
            "START",
            "delivery",
            row.id,
            public(row),
            public(delivery(db, row.id, user)),
        )
    result = trip_detail(db, trip_id, user)
    audit(db, request, user.id, "START", "trip", trip_id, public(before), public(result))
    return result

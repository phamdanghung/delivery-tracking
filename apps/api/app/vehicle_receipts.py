import hashlib
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID, uuid5

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import AwareDatetime, ConfigDict, Field, ValidationError
from sqlalchemy import select, text
from sqlalchemy.engine import Connection
from starlette.concurrency import run_in_threadpool

from app.auth import Db, Operator, User
from app.config import get_settings
from app.database import audit, table
from app.expense_schemas import ReceiptUrl
from app.gps import find_vehicle
from app.pod_exif import strip_exif
from app.pod_images import validate_image
from app.pod_storage import storage_client, store_original
from app.schemas import Input, UserOut

router = APIRouter(prefix="/api/v1", tags=["vehicle-receipts"])


class VehicleReceiptMetadata(Input):
    client_action_id: UUID
    vehicle_id: UUID
    kind: Literal["FUEL", "MAINTENANCE"]
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source: Literal["CAMERA_CAPTURED", "ALBUM_SELECTED"]
    captured_at: AwareDatetime


class VehicleReceiptOut(VehicleReceiptMetadata):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    created_by: UUID
    uploaded_at: datetime
    original_sha256: str
    size_bytes: int


def receipt_digest(metadata: VehicleReceiptMetadata) -> str:
    return hashlib.sha256(metadata.model_dump_json().encode()).hexdigest()


def bind_receipt(
    db: Connection,
    metadata: VehicleReceiptMetadata | None,
    vehicle_id: UUID,
    kind: str,
    actor: UUID,
) -> UUID | None:
    if metadata is None:
        return None
    identifier = uuid5(actor, "vehicle-receipt:" + str(metadata.client_action_id))
    entity = table("vehicle_receipts", db)
    receipt = db.execute(select(entity).where(entity.c.id == identifier)).mappings().first()
    if (
        receipt is None
        or metadata.vehicle_id != vehicle_id
        or metadata.kind != kind
        or receipt["created_by"] != actor
        or receipt["vehicle_id"] != vehicle_id
        or receipt["kind"] != kind
        or receipt["request_hash"] != receipt_digest(metadata)
    ):
        raise HTTPException(
            409, "Chứng từ chưa khớp đúng xe/loại/người nhập/thao tác; giữ ảnh để kiểm tra"
        )
    return identifier


def persist(
    metadata: VehicleReceiptMetadata,
    data: bytes,
    mime: str,
    user: UserOut,
    request: Request,
    db: Connection,
) -> VehicleReceiptOut:
    if user.role not in ("ADMIN", "DISPATCHER") or (
        metadata.kind == "MAINTENANCE" and user.role != "ADMIN"
    ):
        raise HTTPException(403, "Không có quyền tải chứng từ của nghiệp vụ này")
    db.execute(text("SELECT pg_advisory_xact_lock(73210402)"))
    find_vehicle(db, metadata.vehicle_id)
    settings = get_settings()
    info = validate_image(data, mime, settings)
    if mime != metadata.content_type or info.sha256 != metadata.sha256:
        raise HTTPException(422, "Nội dung / định dạng chứng từ không khớp metadata")
    entity = table("vehicle_receipts", db)
    digest = receipt_digest(metadata)
    old = (
        db.execute(
            select(entity).where(
                entity.c.created_by == user.id,
                entity.c.client_action_id == metadata.client_action_id,
            )
        )
        .mappings()
        .first()
    )
    if old:
        if old["request_hash"] != digest:
            raise HTTPException(409, "client_action_id đã dùng cho chứng từ khác")
        return VehicleReceiptOut.model_validate(old)
    clean = strip_exif(data, mime)
    stored = validate_image(clean, mime, settings)
    identifier = uuid5(user.id, "vehicle-receipt:" + str(metadata.client_action_id))
    key = f"vehicle-receipts/{metadata.kind.lower()}/{metadata.vehicle_id}/{identifier}"
    version = store_original(settings, key, clean, stored)
    row = (
        db.execute(
            entity.insert()
            .values(
                **metadata.model_dump(exclude={"sha256"}),
                id=identifier,
                created_by=user.id,
                request_hash=digest,
                object_key=key,
                object_version=version,
                sha256=stored.sha256,
                original_sha256=info.sha256,
                size_bytes=stored.size_bytes,
            )
            .returning(entity)
        )
        .mappings()
        .one()
    )
    result = VehicleReceiptOut.model_validate(row)
    audit(
        db,
        request,
        user.id,
        "UPLOAD",
        "vehicle_receipt",
        identifier,
        after=result.model_dump(mode="json"),
    )
    return result


@router.post(
    "/vehicle-receipts",
    response_model=VehicleReceiptOut,
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                mime: {"schema": {"type": "string", "format": "binary"}}
                for mime in ("image/jpeg", "image/png", "image/webp")
            },
        }
    },
)
async def upload(
    request: Request,
    user: User,
    db: Db,
    x_receipt_metadata: Annotated[str, Header(max_length=8192)],
) -> VehicleReceiptOut:
    if user.role == "DRIVER":
        raise HTTPException(403, "Tài xế chỉ tải biên lai chi phí chuyến của mình")
    try:
        metadata = VehicleReceiptMetadata.model_validate_json(x_receipt_metadata)
    except ValidationError as exc:
        raise HTTPException(422, "Metadata chứng từ không hợp lệ") from exc
    if metadata.kind == "MAINTENANCE" and user.role != "ADMIN":
        raise HTTPException(403, "Chỉ ADMIN được ghi chứng từ bảo dưỡng")
    data = bytearray()
    async for part in request.stream():
        if len(data) + len(part) > get_settings().pod_max_bytes:
            raise HTTPException(413, "Chứng từ vượt giới hạn dung lượng")
        data.extend(part)
    return await run_in_threadpool(
        persist, metadata, bytes(data), request.headers.get("content-type", ""), user, request, db
    )


def read_url(
    db: Connection, identifier: UUID | None, vehicle_id: UUID, kind: str
) -> dict[str, Any]:
    if identifier is None:
        raise HTTPException(404, "Bản ghi không có chứng từ")
    entity = table("vehicle_receipts", db)
    receipt = (
        db.execute(
            select(entity).where(
                entity.c.id == identifier, entity.c.vehicle_id == vehicle_id, entity.c.kind == kind
            )
        )
        .mappings()
        .first()
    )
    if receipt is None:
        raise HTTPException(404, "Không tìm thấy chứng từ đúng phạm vi")
    settings = get_settings()
    client = storage_client(settings, public=True)
    try:
        return {
            "url": client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.s3_bucket,
                    "Key": receipt["object_key"],
                    "VersionId": receipt["object_version"],
                },
                ExpiresIn=settings.pod_read_url_seconds,
            ),
            "expires_in": settings.pod_read_url_seconds,
        }
    finally:
        client.close()


@router.get("/fuel/entries/{entry_id}/receipt-url", response_model=ReceiptUrl)
def fuel_receipt(entry_id: UUID, user: Operator, db: Db) -> dict[str, Any]:
    entity = table("fuel_entries", db)
    row = db.execute(select(entity).where(entity.c.id == entry_id)).mappings().first()
    if row is None:
        raise HTTPException(404, "Không tìm thấy lần đổ")
    return read_url(db, row["receipt_id"], row["vehicle_id"], "FUEL")


@router.get("/maintenance/events/{event_id}/receipt-url", response_model=ReceiptUrl)
def maintenance_receipt(event_id: UUID, user: Operator, db: Db) -> dict[str, Any]:
    entity = table("maintenance_events", db)
    row = db.execute(select(entity).where(entity.c.id == event_id)).mappings().first()
    if row is None:
        raise HTTPException(404, "Không tìm thấy lần bảo dưỡng")
    return read_url(db, row["receipt_id"], row["vehicle_id"], "MAINTENANCE")

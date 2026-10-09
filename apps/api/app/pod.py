"""M5 authenticated photo upload, attempt binding and private evidence access."""

import hashlib
from typing import Annotated, Any
from uuid import UUID, uuid5

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from app.auth import Db, User
from app.config import get_settings
from app.database import audit
from app.deliveries import delivery, lock_delivery
from app.pod_exif import strip_exif
from app.pod_images import validate_image
from app.pod_metadata import PodMetadata
from app.pod_schemas import PodPhotoOut, PodReadUrl
from app.pod_storage import storage_client, store_original

router = APIRouter(prefix="/api/v1", tags=["pod"])
SELECT = """SELECT id,delivery_id,trip_stop_id,source,captured_at,uploaded_at,
  ST_Y(location::geometry) AS latitude,ST_X(location::geometry) AS longitude,
  location_status,gps_fix_at,gps_freshness,location_reason,sha256,original_sha256,
  sync_id,created_by,content_type,size_bytes FROM pod_photos"""


def acknowledge_photo(
    delivery_id: UUID, metadata: PodMetadata, user: User, db: Db
) -> dict[str, Any]:
    before = lock_delivery(db, delivery_id, user)
    row = (
        db.execute(
            text(SELECT + " WHERE sync_id=:sync AND created_by=:actor"),
            {"sync": str(metadata.client_action_id), "actor": user.id},
        )
        .mappings()
        .first()
    )
    stop = db.scalar(
        text("SELECT id FROM trip_stops WHERE id=:stop AND trip_id=:trip AND delivery_id=:id"),
        {"stop": metadata.trip_stop_id, "trip": before.trip_id, "id": delivery_id},
    )
    if (
        row is None
        or not stop
        or row["delivery_id"] != delivery_id
        or row["trip_stop_id"] != metadata.trip_stop_id
        or row["original_sha256"] != metadata.sha256
        or row["source"] != metadata.source
    ):
        raise HTTPException(
            409, "Ảnh POD chưa được chấp nhận cho lượt giao hiện tại; xem dữ liệu mới"
        )
    expected_hash = hashlib.sha256(
        (str(delivery_id) + row["content_type"] + metadata.model_dump_json()).encode()
    ).hexdigest()
    actual_hash = db.scalar(
        text("SELECT request_hash FROM pod_photos WHERE id=:id"), {"id": row["id"]}
    )
    if expected_hash != actual_hash:
        raise HTTPException(409, "Metadata POD không khớp command đã upload; không sửa command cũ")
    return dict(row)


def persist_photo(
    delivery_id: UUID,
    metadata: PodMetadata,
    data: bytes,
    content_type: str,
    user: User,
    request: Request,
    db: Db,
) -> dict[str, Any]:
    if user.role != "DRIVER":
        raise HTTPException(403, "Chỉ tài xế được tải ảnh POD")
    settings = get_settings()
    original = validate_image(data, content_type, settings)
    if original.sha256 != metadata.sha256:
        raise HTTPException(422, "Hash ảnh không khớp; giữ ảnh gốc để kiểm tra")
    before = lock_delivery(db, delivery_id, user)
    digest = hashlib.sha256(
        (str(delivery_id) + content_type + metadata.model_dump_json()).encode()
    ).hexdigest()
    old = (
        db.execute(
            text("SELECT id,created_by,request_hash FROM pod_photos WHERE sync_id=:sync"),
            {"sync": str(metadata.client_action_id)},
        )
        .mappings()
        .first()
    )
    if old:
        if old["created_by"] != user.id or old["request_hash"] != digest:
            raise HTTPException(409, "client_action_id đã dùng cho ảnh/metadata khác")
        return dict(db.execute(text(SELECT + " WHERE id=:id"), {"id": old["id"]}).mappings().one())
    stop = db.execute(
        text(
            "SELECT id FROM trip_stops WHERE id=:stop AND delivery_id=:delivery AND trip_id=:trip"
        ),
        {"stop": metadata.trip_stop_id, "delivery": delivery_id, "trip": before.trip_id},
    ).scalar()
    trip_status = db.scalar(text("SELECT status FROM trips WHERE id=:id"), {"id": before.trip_id})
    if not stop or trip_status != "ACTIVE" or before.status != "DELIVERING":
        raise HTTPException(409, "POD cần đúng lượt giao hiện tại đang giao hàng; tải lại dữ liệu")
    clean = strip_exif(data, content_type)
    info = validate_image(clean, content_type, settings)
    identifier = uuid5(user.id, str(metadata.client_action_id))
    key = f"pod/{delivery_id}/{metadata.trip_stop_id}/{identifier}"
    version = store_original(settings, key, clean, info)
    values = {
        **metadata.model_dump(),
        "id": identifier,
        "delivery": delivery_id,
        "key": key,
        "version": version,
        "actor": user.id,
        "hash": digest,
        "stored_sha": info.sha256,
        "mime": info.content_type,
        "size": info.size_bytes,
        "sync": str(metadata.client_action_id),
    }
    db.execute(
        text("""INSERT INTO pod_photos
      (id,delivery_id,trip_stop_id,object_key,captured_at,uploaded_at,location,sha256,sync_id,
       created_by,source,location_status,gps_fix_at,gps_freshness,location_reason,
       original_sha256,request_hash,object_version,content_type,size_bytes)
      VALUES (:id,:delivery,:trip_stop_id,:key,:captured_at,now(),
       CASE WHEN CAST(:latitude AS double precision) IS NULL THEN NULL ELSE
       ST_SetSRID(ST_MakePoint(:longitude,:latitude),4326)::geography END,
       :stored_sha,:sync,:actor,:source,:location_status,:gps_fix_at,:gps_freshness,
       :location_reason,:sha256,:hash,:version,:mime,:size)"""),
        values,
    )
    result = dict(db.execute(text(SELECT + " WHERE id=:id"), {"id": identifier}).mappings().one())
    audit(
        db, request, user.id, "POD_UPLOAD", "delivery", delivery_id, after=jsonable_encoder(result)
    )
    db.execute(
        text("""UPDATE audit_logs SET reason=:reason
      WHERE request_id=:request AND actor_user_id=:actor AND action='POD_UPLOAD'
      AND resource_type='delivery' AND resource_id=:delivery"""),
        {
            "reason": metadata.location_reason,
            "request": request.state.request_id,
            "actor": user.id,
            "delivery": str(delivery_id),
        },
    )
    return result


@router.post("/deliveries/{delivery_id}/pod/photos", status_code=201, response_model=PodPhotoOut)
async def upload_photo(
    delivery_id: UUID,
    request: Request,
    user: User,
    db: Db,
    x_pod_metadata: Annotated[str, Header(max_length=8192)],
) -> dict[str, Any]:
    if user.role != "DRIVER":
        raise HTTPException(403, "Chỉ tài xế được tải ảnh POD")
    try:
        metadata = PodMetadata.model_validate_json(x_pod_metadata)
    except ValidationError as error:
        raise HTTPException(
            422, "Metadata POD không hợp lệ; kiểm tra vị trí/lý do và nguồn ảnh"
        ) from error
    chunks = bytearray()
    async for chunk in request.stream():
        if len(chunks) + len(chunk) > get_settings().pod_max_bytes:
            raise HTTPException(413, "Ảnh vượt giới hạn dung lượng POD")
        chunks.extend(chunk)
    return await run_in_threadpool(
        persist_photo,
        delivery_id,
        metadata,
        bytes(chunks),
        request.headers.get("content-type", ""),
        user,
        request,
        db,
    )


@router.get("/deliveries/{delivery_id}/pod/photos", response_model=list[PodPhotoOut])
def list_photos(delivery_id: UUID, user: User, db: Db) -> list[dict[str, Any]]:
    delivery(db, delivery_id, user)
    return [
        dict(row)
        for row in db.execute(
            text(SELECT + " WHERE delivery_id=:id ORDER BY uploaded_at,id"), {"id": delivery_id}
        ).mappings()
    ]


@router.get("/deliveries/{delivery_id}/pod/photos/{photo_id}/url", response_model=PodReadUrl)
def photo_url(delivery_id: UUID, photo_id: UUID, user: User, db: Db) -> dict[str, Any]:
    delivery(db, delivery_id, user)
    row = (
        db.execute(
            text(
                "SELECT object_key,object_version FROM pod_photos "
                "WHERE id=:photo AND delivery_id=:delivery"
            ),
            {"photo": photo_id, "delivery": delivery_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Không tìm thấy ảnh POD")
    settings = get_settings()
    client = storage_client(settings, public=True)
    try:
        params = {"Bucket": settings.s3_bucket, "Key": row["object_key"]}
        if row["object_version"]:
            params["VersionId"] = row["object_version"]
        url = client.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=settings.pod_read_url_seconds
        )
        return {"url": url, "expires_in": settings.pod_read_url_seconds}
    finally:
        client.close()

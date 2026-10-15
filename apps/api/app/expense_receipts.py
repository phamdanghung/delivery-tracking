import hashlib
from typing import Annotated, Any
from uuid import UUID, uuid5

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import select, text
from starlette.concurrency import run_in_threadpool

from app.auth import Db, User
from app.config import get_settings
from app.database import audit, table
from app.expense_schemas import ReceiptMetadata, ReceiptOut, ReceiptUrl
from app.expenses import scoped_expense, writable_trip
from app.fuel import encoded, record
from app.pod_exif import strip_exif
from app.pod_images import validate_image
from app.pod_storage import storage_client, store_original

router = APIRouter(prefix="/api/v1", tags=["expense-receipts"])


def persist_receipt(
    metadata: ReceiptMetadata, data: bytes, mime: str, user: User, request: Request, db: Db
) -> ReceiptOut:
    db.execute(text("SELECT pg_advisory_xact_lock(73210402)"))
    settings = get_settings()
    original = validate_image(data, mime, settings)
    if metadata.content_type != mime:
        raise HTTPException(422, "Định dạng biên lai không khớp metadata")
    if original.sha256 != metadata.sha256:
        raise HTTPException(422, "Hash biên lai không khớp; giữ ảnh gốc để kiểm tra")
    digest = hashlib.sha256((mime + metadata.model_dump_json()).encode()).hexdigest()
    entity = table("expense_receipts", db)
    before = (
        db.execute(
            select(entity).where(
                entity.c.created_by == user.id,
                entity.c.client_action_id == metadata.client_action_id,
            )
        )
        .mappings()
        .first()
    )
    if before:
        if before["request_hash"] != digest:
            raise HTTPException(409, "client_action_id đã dùng cho biên lai khác")
        return ReceiptOut.model_validate(before)
    writable_trip(db, metadata.trip_id, user)
    clean = strip_exif(data, mime)
    info = validate_image(clean, mime, settings)
    identifier = uuid5(user.id, "receipt:" + str(metadata.client_action_id))
    key = f"expense-receipts/{metadata.trip_id}/{identifier}"
    version = store_original(settings, key, clean, info)
    values = metadata.model_dump(exclude={"sha256", "content_type"})
    row = (
        db.execute(
            entity.insert()
            .values(
                **values,
                id=identifier,
                created_by=user.id,
                request_hash=digest,
                object_key=key,
                object_version=version,
                sha256=info.sha256,
                original_sha256=original.sha256,
                content_type=mime,
                size_bytes=info.size_bytes,
            )
            .returning(entity)
        )
        .mappings()
        .one()
    )
    result = ReceiptOut.model_validate(row)
    audit(db, request, user.id, "UPLOAD", "expense_receipt", identifier, after=encoded(result))
    return result


@router.post(
    "/expense-receipts",
    response_model=ReceiptOut,
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
async def receipt_upload(
    request: Request,
    user: User,
    db: Db,
    x_receipt_metadata: Annotated[str, Header(max_length=8192)],
) -> ReceiptOut:
    if user.role not in ("DRIVER", "DISPATCHER"):
        raise HTTPException(403, "Chỉ tài xế/điều phối được tải biên lai chi phí")
    try:
        metadata = ReceiptMetadata.model_validate_json(x_receipt_metadata)
    except ValidationError as exc:
        raise HTTPException(422, "Metadata biên lai không hợp lệ") from exc
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > get_settings().pod_max_bytes:
            raise HTTPException(413, "Ảnh biên lai vượt giới hạn dung lượng")
        data.extend(chunk)
    return await run_in_threadpool(
        persist_receipt,
        metadata,
        bytes(data),
        request.headers.get("content-type", ""),
        user,
        request,
        db,
    )


@router.get("/expenses/{expense_id}/receipt-url", response_model=ReceiptUrl)
def receipt_url(expense_id: UUID, user: User, db: Db) -> dict[str, Any]:
    expense = scoped_expense(db, expense_id, user)
    if expense["receipt_id"] is None:
        raise HTTPException(404, "Chi phí không có biên lai")
    receipt = record(db, "expense_receipts", expense["receipt_id"])
    if receipt["trip_id"] != expense["trip_id"] or receipt["created_by"] != expense["created_by"]:
        raise HTTPException(409, "Biên lai không khớp chi phí")
    settings = get_settings()
    client = storage_client(settings, public=True)
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.s3_bucket,
                "Key": receipt["object_key"],
                "VersionId": receipt["object_version"],
            },
            ExpiresIn=settings.pod_read_url_seconds,
        )
        return {"url": url, "expires_in": settings.pod_read_url_seconds}
    finally:
        client.close()

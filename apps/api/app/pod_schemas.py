from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class PodPhotoOut(BaseModel):
    id: UUID
    delivery_id: UUID
    trip_stop_id: UUID | None
    source: Literal["CAMERA_CAPTURED", "ALBUM_SELECTED"] | None
    captured_at: datetime
    uploaded_at: datetime | None
    latitude: float | None
    longitude: float | None
    location_status: Literal["VERIFIED", "LOCATION_UNVERIFIED"] | None
    gps_fix_at: datetime | None
    gps_freshness: str | None
    location_reason: str | None
    sha256: str | None
    original_sha256: str | None
    sync_id: str | None
    created_by: UUID | None
    content_type: str | None
    size_bytes: int | None


class PodReadUrl(BaseModel):
    url: str
    expires_in: int

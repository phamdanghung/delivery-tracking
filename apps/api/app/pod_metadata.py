"""Business metadata comes from the command, never image EXIF (DEC-037/038)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.gps import freshness
from app.schemas import Input


class PodMetadata(Input):
    client_action_id: UUID
    trip_stop_id: UUID
    source: Literal["CAMERA_CAPTURED", "ALBUM_SELECTED"]
    captured_at: datetime
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    location_status: Literal["VERIFIED", "LOCATION_UNVERIFIED"]
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    gps_fix_at: datetime | None = None
    gps_freshness: Literal["NORMAL", "STALE", "INVALID", "MISSING"]
    location_reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def valid_metadata(self) -> "PodMetadata":
        if self.captured_at.tzinfo is None or (
            self.gps_fix_at is not None and self.gps_fix_at.tzinfo is None
        ):
            raise ValueError("Thời điểm POD/GPS phải có timezone")
        if self.location_status == "VERIFIED":
            if (
                self.latitude is None
                or self.longitude is None
                or self.gps_fix_at is None
                or self.gps_freshness != "NORMAL"
            ):
                raise ValueError("GPS xác minh cần tọa độ/fix time và freshness NORMAL")
            if freshness(self.gps_fix_at, self.gps_fix_at, self.captured_at) != "NORMAL":
                raise ValueError(
                    "GPS fix không thuộc thời điểm capture/select; cần lý do chưa xác minh"
                )
        else:
            if not self.location_reason or not self.location_reason.strip():
                raise ValueError("Tài xế phải xác nhận lý do vị trí chưa xác minh")
            if self.latitude is not None or self.longitude is not None:
                raise ValueError("Không lưu tọa độ chưa xác minh như vị trí chụp hiện tại")
        return self

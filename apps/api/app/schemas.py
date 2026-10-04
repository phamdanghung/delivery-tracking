from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Role(StrEnum):
    ADMIN = "ADMIN"
    DISPATCHER = "DISPATCHER"
    DRIVER = "DRIVER"


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Input):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class Refresh(Input):
    refresh_token: str = Field(min_length=32, max_length=256)


class UserOut(BaseModel):
    id: UUID
    full_name: str
    email: str | None
    phone: str | None
    role: Role
    is_active: bool


class UserCreate(Input):
    full_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=254)
    phone: str | None = Field(default=None, max_length=32)
    password: str = Field(min_length=12, max_length=256)
    role: Role

    @field_validator("email")
    @classmethod
    def email_address(cls, value: str) -> str:
        if value.count("@") != 1 or " " in value:
            raise ValueError("Email không hợp lệ")
        return value.casefold()


class UserUpdate(Input):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=12, max_length=256)


class VehicleInput(Input):
    plate_no: str = Field(min_length=1, max_length=32)
    name: str | None = Field(default=None, max_length=200)
    vehicle_type: str | None = Field(default=None, max_length=100)
    max_weight_kg: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    max_volume_m3: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    traccar_device_id: int | None = Field(default=None, gt=0)
    status: str = Field(default="ACTIVE", min_length=1, max_length=32)

    @field_validator("plate_no")
    @classmethod
    def normalize_plate(cls, value: str) -> str:
        return value.upper()


class VehicleOut(VehicleInput):
    model_config = ConfigDict(extra="ignore")
    id: UUID


class DriverInput(Input):
    user_id: UUID
    active: bool = True


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class GpsPosition(BaseModel):
    position_id: int | None
    traccar_device_id: int | None
    latitude: float | None
    longitude: float | None
    speed_kmh: float | None
    course: float | None
    gps_at: datetime | None
    server_received_at: datetime | None
    backend_received_at: datetime
    acc: bool | None
    engine_state: Literal["MOVING", "IDLING", "PARKED", "UNKNOWN"]
    valid: bool
    freshness: Literal["NORMAL", "STALE", "LOST"]
    position_label: str


class LivePosition(BaseModel):
    vehicle_id: UUID
    position: GpsPosition | None
    freshness: Literal["NORMAL", "STALE", "LOST"]
    reason: str | None

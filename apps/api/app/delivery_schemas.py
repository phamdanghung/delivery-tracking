from datetime import date, datetime
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.schemas import Input

Status = Literal[
    "CREATED",
    "PLANNED",
    "ASSIGNED",
    "EN_ROUTE",
    "ARRIVED",
    "DELIVERING",
    "DELIVERED",
    "FAILED",
    "RESCHEDULED",
    "CANCELLED",
]


class Commitment(Input):
    commitment_type: Literal["FIXED_TIME", "TIME_WINDOW", "BEFORE_DEADLINE"]
    scheduled_date: date
    appointment_at: AwareDatetime | None = None
    window_start: AwareDatetime | None = None
    window_end: AwareDatetime | None = None
    deadline_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def valid_commitment(self) -> Self:
        if self.commitment_type == "FIXED_TIME" and self.appointment_at is None:
            raise ValueError("Giờ cố định bắt buộc appointment_at")
        if self.commitment_type == "TIME_WINDOW" and (
            self.window_start is None
            or self.window_end is None
            or self.window_start > self.window_end
        ):
            raise ValueError("Khung giờ cần start <= end")
        if self.commitment_type == "BEFORE_DEADLINE" and self.deadline_at is None:
            raise ValueError("Giao trước mốc bắt buộc deadline_at")
        permitted = {
            "FIXED_TIME": {"appointment_at"},
            "TIME_WINDOW": {"window_start", "window_end"},
            "BEFORE_DEADLINE": {"deadline_at"},
        }[self.commitment_type]
        if any(
            getattr(self, name) is not None
            for name in {"appointment_at", "window_start", "window_end", "deadline_at"} - permitted
        ):
            raise ValueError("Chỉ điền thời gian tương ứng kiểu hẹn")
        return self


class DeliveryInput(Commitment):
    recipient_name: str = Field(min_length=1, max_length=200)
    recipient_phone: str = Field(min_length=1, max_length=32)
    address_text: str = Field(min_length=1, max_length=1000)
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    weight_kg: float | None = Field(default=None, ge=0, le=9999999999.99, allow_inf_nan=False)
    volume_m3: float | None = Field(default=None, ge=0, le=999999999.999, allow_inf_nan=False)
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def coordinate_pair(self) -> Self:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Tọa độ cần đủ latitude và longitude")
        return self


class DeliveryOut(BaseModel):
    id: UUID
    code: str
    recipient_name: str
    recipient_phone: str
    address_text: str
    latitude: float | None
    longitude: float | None
    commitment_type: str | None
    appointment_at: datetime | None
    window_start: datetime | None
    window_end: datetime | None
    deadline_at: datetime | None
    scheduled_date: date | None
    weight_kg: float | None
    volume_m3: float | None
    notes: str | None
    status: Status
    trip_id: UUID | None = None
    vehicle_id: UUID | None = None
    driver_id: UUID | None = None
    plate_no: str | None = None
    driver_name: str | None = None
    eta_at: datetime | None = None


class StatusCommand(Input):
    from_status: Status
    to_status: Status
    reason: str | None = Field(default=None, min_length=1, max_length=2000)
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)

    @model_validator(mode="after")
    def coordinate_pair(self) -> Self:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Tọa độ cần đủ latitude và longitude")
        return self


class RescheduleInput(Input):
    commitment: Commitment | None = None
    proposal_id: UUID | None = None

    @model_validator(mode="after")
    def exclusive(self) -> Self:
        if (self.commitment is None) == (self.proposal_id is None):
            raise ValueError("Chọn commitment mới hoặc proposal_id để xác nhận")
        return self


class Point(Input):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)


class TripInput(Input):
    trip_date: date
    vehicle_id: UUID
    driver_id: UUID
    delivery_ids: list[UUID] = Field(min_length=1, max_length=100)
    start: Point | None = None
    end: Point | None = None

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len(set(self.delivery_ids)) != len(self.delivery_ids):
            raise ValueError("Đơn không được lặp trong chuyến")
        return self


class TripOut(BaseModel):
    id: UUID
    trip_date: date
    vehicle_id: UUID
    driver_id: UUID
    plate_no: str
    driver_name: str
    status: Literal["DRAFT", "PLANNED", "ACTIVE", "COMPLETED", "CANCELLED"]
    start: Point | None
    end: Point | None
    weight_kg: float
    volume_m3: float
    warnings: list[str]
    stops: list[dict[str, object]]


class DeliveryEventOut(BaseModel):
    id: UUID
    from_status: Status | None
    to_status: Status
    event_time: datetime
    source: str
    reason: str | None
    actor_user_id: UUID | None
    actor_name: str | None
    request_id: str | None
    latitude: float | None
    longitude: float | None


class RescheduleProposalOut(BaseModel):
    id: UUID
    delivery_id: UUID
    failure_event_id: UUID
    proposed_by: UUID
    proposer_name: str
    commitment_type: str
    scheduled_date: date
    appointment_at: datetime | None
    window_start: datetime | None
    window_end: datetime | None
    deadline_at: datetime | None
    created_at: datetime
    confirmed_by: UUID | None
    confirmed_at: datetime | None


class DeliveryDetailOut(BaseModel):
    delivery: DeliveryOut
    events: list[DeliveryEventOut]
    reschedule_proposals: list[RescheduleProposalOut]
    audit: list[dict[str, Any]]


class RescheduleOut(BaseModel):
    confirmed: bool
    delivery: DeliveryOut
    proposal_id: UUID | None = None


class TripConfigOut(BaseModel):
    configured: bool
    company: Point | None
    message: str | None

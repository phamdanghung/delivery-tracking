from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, ConfigDict, Field, model_validator

from app.schemas import Input


class SafetyConfigInput(Input):
    speed_limit_kmh: Decimal | None = Field(default=None, gt=0, max_digits=8, decimal_places=3)
    outside_hours_enabled: bool = True
    reason: str = Field(min_length=1, max_length=2000)


class SafetyConfigOut(Input):
    vehicle_id: UUID
    speed_limit_kmh: Decimal | None
    outside_hours_enabled: bool


class SafetyExceptionInput(Input):
    vehicle_id: UUID
    type: Literal["SPEEDING", "OUTSIDE_HOURS"]
    from_at: AwareDatetime
    to_at: AwareDatetime
    reason: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def period(self) -> "SafetyExceptionInput":
        if self.from_at >= self.to_at:
            raise ValueError("Ngoại lệ cần FROM < TO, có thời hạn")
        return self


class SafetyExceptionOut(SafetyExceptionInput):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    created_by: UUID
    created_at: datetime
    deleted_at: datetime | None


class SafetyStateInput(Input):
    from_state: Literal["NEW", "SEEN"]
    to_state: Literal["SEEN", "RESOLVED"]
    reason: str | None = Field(default=None, min_length=1, max_length=2000)

    @model_validator(mode="after")
    def resolution(self) -> "SafetyStateInput":
        if self.to_state == "RESOLVED" and not self.reason:
            raise ValueError("RESOLVED bắt buộc lý do")
        return self


class SafetyAlertOut(Input):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    vehicle_id: UUID
    type: str
    event_time: datetime
    severity: str
    payload_json: dict[str, Any]
    status: Literal["NEW", "SEEN", "RESOLVED"]
    seen_by: UUID | None
    seen_at: datetime | None
    resolved_by: UUID | None
    resolved_at: datetime | None
    resolution_reason: str | None
    incident_ended_at: datetime | None
    last_event_at: datetime | None
    source_position_id: int | None

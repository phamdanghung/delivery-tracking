from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class OptimizeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    planned_departure_at: AwareDatetime
    service_seconds: dict[UUID, int] = Field(default_factory=dict)


class ApproveInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: UUID


class RoutingConfigOut(BaseModel):
    configured: bool
    message: str | None
    fixed_time_tolerance_seconds: int
    default_service_seconds: int


class RouteStopOut(BaseModel):
    stop_id: UUID
    delivery_id: UUID
    sequence_no: int
    recipient_name: str
    address_text: str
    latitude: float
    longitude: float
    commitment_type: str
    window_start: datetime | None
    window_end: datetime
    arrival_at: datetime
    service_seconds: int
    violation_seconds: int
    violation: str | None


class RoutePlanOut(BaseModel):
    id: UUID
    trip_id: UUID
    planned_departure_at: datetime
    distance_m: int
    duration_s: int
    stops: list[RouteStopOut]
    geometry: dict[str, Any]
    route_detail: dict[str, Any]
    warnings: list[str]
    time_feasible: bool
    approval_allowed: bool
    stale: bool = False
    approved: bool = False
    proven_objectives: tuple[bool, ...]
    solver_seconds: float
    dataset_sha256: str

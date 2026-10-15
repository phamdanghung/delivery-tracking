from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, ConfigDict, Field, model_validator

from app.schemas import Input
from app.vehicle_receipts import VehicleReceiptMetadata


class MaintenanceRuleInput(Input):
    vehicle_id: UUID
    task_type: str = Field(min_length=1, max_length=100)
    interval_km: int | None = Field(default=None, gt=0)
    interval_days: int | None = Field(default=None, gt=0)
    lead_km: int | None = Field(default=None, ge=0)
    lead_days: int | None = Field(default=None, ge=0)
    baseline_date: date | None = None
    baseline_odometer_km: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=1
    )
    baseline_source: Literal["ADMIN"] | None = None
    active: bool = True

    @model_validator(mode="after")
    def thresholds(self) -> "MaintenanceRuleInput":
        if self.interval_km is None and self.interval_days is None:
            raise ValueError("Cần ngưỡng km hoặc ngày")
        if self.interval_km is not None and (self.lead_km is None):
            raise ValueError("Nhập lead_km tường minh")
        if self.interval_days is not None and (self.lead_days is None):
            raise ValueError("Nhập lead_days tường minh")
        if (
            self.baseline_date is not None or self.baseline_odometer_km is not None
        ) and self.baseline_source is None:
            raise ValueError("Mốc khởi tạo phải ghi nguồn ADMIN")
        return self


class MaintenanceRuleUpdate(MaintenanceRuleInput):
    reason: str = Field(min_length=1, max_length=2000)


class MaintenanceRuleOut(Input):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    vehicle_id: UUID
    task_type: str
    interval_km: int | None
    interval_days: int | None
    lead_km: int | None
    lead_days: int | None
    baseline_date: date | None
    baseline_odometer_km: Decimal | None
    baseline_source: str | None
    active: bool


class MaintenanceEventInput(Input):
    rule_id: UUID
    vehicle_id: UUID
    service_date: date
    odometer_km: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=1)
    odometer_source: Literal["ADMIN"] | None = None
    note: str | None = Field(default=None, max_length=2000)
    cost: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    receipt_metadata: VehicleReceiptMetadata | None = None

    @model_validator(mode="after")
    def reading_source(self) -> "MaintenanceEventInput":
        if self.odometer_km is not None and self.odometer_source is None:
            raise ValueError("Odometer nhập phải ghi nguồn ADMIN")
        return self


class MaintenanceEventCreate(MaintenanceEventInput):
    client_action_id: UUID


class MaintenanceEventOut(Input):
    model_config = ConfigDict(extra="ignore")
    rule_id: UUID | None
    vehicle_id: UUID
    service_date: date
    odometer_km: Decimal | None
    odometer_source: Literal["ADMIN", "TRACCAR"] | None
    note: str | None
    cost: Decimal | None
    id: UUID
    task_type: str
    created_by: UUID | None
    created_at: datetime
    receipt_id: UUID | None
    client_action_id: UUID | None


class OdometerInput(Input):
    vehicle_id: UUID
    odometer_km: Decimal = Field(ge=0, max_digits=12, decimal_places=1)
    observed_at: AwareDatetime
    reason: str = Field(min_length=1, max_length=2000)


class OdometerOut(OdometerInput):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    source: Literal["ADMIN", "TRACCAR"]
    created_by: UUID | None


class MaintenanceStatusOut(Input):
    rule: MaintenanceRuleOut
    odometer: OdometerOut | None
    assessment: dict[str, Any]


class VehicleDocumentInput(Input):
    vehicle_id: UUID
    doc_type: str = Field(min_length=1, max_length=100)
    expiry_date: date
    lead_days: int = Field(default=30, ge=0)


class VehicleDocumentUpdate(VehicleDocumentInput):
    reason: str = Field(min_length=1, max_length=2000)


class VehicleDocumentOut(VehicleDocumentInput):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    remaining_days: int
    status: Literal["NOT_DUE", "SOON", "DUE", "OVERDUE"]

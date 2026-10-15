from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, ConfigDict, Field, model_validator

from app.schemas import Input
from app.vehicle_receipts import VehicleReceiptMetadata


class FuelProfileInput(Input):
    vehicle_id: UUID
    driving_l_per_100km: Decimal = Field(ge=0, max_digits=8, decimal_places=3)
    idling_l_per_hour: Decimal = Field(ge=0, max_digits=8, decimal_places=3)
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def dates(self) -> "FuelProfileInput":
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to phải sau effective_from")
        return self


class FuelProfileOut(FuelProfileInput):
    model_config = ConfigDict(extra="ignore")
    id: UUID


class FuelEntryInput(Input):
    vehicle_id: UUID
    trip_id: UUID | None = None
    liters: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    filled_at: AwareDatetime
    note: str | None = Field(default=None, max_length=2000)
    receipt_metadata: VehicleReceiptMetadata | None = None


class FuelEntryCreate(FuelEntryInput):
    client_action_id: UUID


class FuelEntryUpdate(FuelEntryInput):
    reason: str = Field(min_length=1, max_length=2000)
    client_action_id: UUID | None = None


class FuelEntryOut(FuelEntryInput):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    created_by: UUID | None
    deleted_at: datetime | None
    receipt_metadata: None = Field(default=None, exclude=True)
    receipt_id: UUID | None
    client_action_id: UUID | None


class ReconciliationInput(Input):
    vehicle_id: UUID
    from_at: AwareDatetime
    to_at: AwareDatetime

    @model_validator(mode="after")
    def period(self) -> "ReconciliationInput":
        if self.from_at >= self.to_at:
            raise ValueError("FROM phải trước TO")
        return self


class Recompute(Input):
    reason: str = Field(min_length=1, max_length=2000)


class ReconciliationOut(ReconciliationInput):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    status: Literal["DRAFT", "FINAL"]
    created_by: UUID
    created_at: datetime
    versions: list[dict[str, Any]]

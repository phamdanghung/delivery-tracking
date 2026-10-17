from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ReportPeriod(BaseModel):
    date_from: date
    date_to: date
    timezone: Literal["Asia/Bangkok"] = "Asia/Bangkok"
    vehicle_id: UUID | None


class ReportCommitment(BaseModel):
    route_plan_id: UUID
    type: Literal["FIXED_TIME", "TIME_WINDOW", "BEFORE_DEADLINE"]
    appointment_at: datetime | None
    window_start: datetime | None
    window_end: datetime | None
    deadline_at: datetime | None
    tolerance_seconds: int | None
    valid_from: datetime | None
    valid_to: datetime


class ReportCorrection(BaseModel):
    event_id: UUID
    audit_id: UUID
    at: datetime
    actor_user_id: UUID
    reason: str


class ReportAttempt(BaseModel):
    trip_id: UUID
    trip_date: date | None
    vehicle_id: UUID | None
    delivery_id: UUID
    delivery_code: str
    attempt_id: UUID
    attempt_status: str
    status: Literal["EARLY", "ON_TIME", "LATE", "UNKNOWN"]
    unknown_reasons: list[str]
    commitment: ReportCommitment | None
    arrival_event_id: UUID | None
    arrival_audit_id: UUID | None
    arrived_at: datetime | None
    corrections: list[ReportCorrection]


class ReportSummary(BaseModel):
    period: ReportPeriod
    trips: int
    attempts: int
    failed_attempts: int
    eligible_attempts: int
    early: int
    on_time: int
    late: int
    unknown: int
    on_time_rate: Decimal | None
    early_rate: Decimal | None
    late_rate: Decimal | None


class ReportAttempts(BaseModel):
    period: ReportPeriod
    total: int
    limit: int
    offset: int
    items: list[ReportAttempt]


class ReportVehicle(BaseModel):
    vehicle_id: UUID
    plate_no: str
    trips: int
    attempts: int
    hours_quality: Literal["VALID", "PARTIAL", "UNKNOWN"]
    distance_quality: Literal["VALID", "PARTIAL", "UNKNOWN"]
    hours_coverage_seconds: Decimal
    distance_coverage_seconds: Decimal
    period_seconds: Decimal
    traccar_device_id: int | None
    traccar_device_ids: list[int]
    mapping_audit_ids: list[UUID]
    reasons: list[str]
    distance_km: Decimal | None
    moving_hours: Decimal | None
    idle_hours: Decimal | None
    operating_hours: Decimal | None
    source: Literal["TRACCAR"] = "TRACCAR"


class ReportVehicles(BaseModel):
    period: ReportPeriod
    total: int
    limit: int
    offset: int
    items: list[ReportVehicle]


class ReportReconciliation(BaseModel):
    reconciliation_id: UUID
    vehicle_id: UUID
    from_at: datetime
    to_at: datetime
    version_id: UUID
    version: int
    computed_at: datetime
    data_status: Literal["COMPLETE", "INSUFFICIENT"]
    reasons: list[str]
    actual_liters: Decimal
    expected_liters: Decimal | None
    variance_pct: Decimal | None
    alert_flag: bool


class ReportExcludedReconciliation(BaseModel):
    reconciliation_id: UUID
    reason: str


class ReportFinancialSource(BaseModel):
    source_table: Literal["fuel_entries", "expenses"]
    record_id: UUID
    vehicle_id: UUID | None
    trip_id: UUID | None
    business_date: date
    business_at: datetime
    category: str
    liters: Decimal | None
    amount: Decimal | None
    included: bool
    exclusion_reason: str | None


class ReportFinancialSources(BaseModel):
    period: ReportPeriod
    total: int
    limit: int
    offset: int
    items: list[ReportFinancialSource]


class ReportFinancial(BaseModel):
    period: ReportPeriod
    fuel_entries: int
    total_fuel_liters: Decimal
    total_fuel_cost: Decimal | None
    fuel_missing_amount: int
    expenses: int
    total_trip_expense: Decimal
    expense_by_type: dict[str, Decimal]
    reconciliations: list[ReportReconciliation]
    excluded_reconciliations: list[ReportExcludedReconciliation]
    grand_total: None = None
    grand_total_reason: str


class ReportTelemetryInterval(BaseModel):
    traccar_device_id: int
    mapping_audit_ids: list[UUID]
    from_at: datetime
    to_at: datetime
    seconds: Decimal
    engine_state: Literal["MOVING", "IDLING", "PARKED", "UNKNOWN"]
    position_ids: list[int]
    distance_verified: bool


class ReportVehicleIntervals(BaseModel):
    period: ReportPeriod
    vehicle_id: UUID
    traccar_device_id: int | None
    traccar_device_ids: list[int]
    source: Literal["TRACCAR"] = "TRACCAR"
    mapping_audit_ids: list[UUID]
    total: int
    limit: int
    offset: int
    items: list[ReportTelemetryInterval]
    reasons: list[str]

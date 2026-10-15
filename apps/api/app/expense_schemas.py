from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, ConfigDict, Field

from app.schemas import Input


class ReceiptMetadata(Input):
    client_action_id: UUID
    trip_id: UUID
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    source: Literal["CAMERA_CAPTURED", "ALBUM_SELECTED"]
    captured_at: AwareDatetime


class ExpenseData(Input):
    type: Literal["TOLL", "PARKING", "HANDLING", "OTHER"]
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    note: str | None = Field(default=None, max_length=2000)
    incurred_at: AwareDatetime
    receipt_metadata: ReceiptMetadata | None = None


class ExpenseInput(ExpenseData):
    trip_id: UUID
    client_action_id: UUID


class ExpenseOut(Input):
    model_config = ConfigDict(extra="ignore")
    type: str
    amount: Decimal
    note: str | None
    incurred_at: datetime
    receipt_id: UUID | None
    id: UUID
    trip_id: UUID
    created_by: UUID | None
    client_action_id: UUID | None


class ReceiptOut(Input):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    trip_id: UUID
    created_by: UUID
    client_action_id: UUID
    sha256: str
    original_sha256: str
    content_type: str
    size_bytes: int
    source: Literal["CAMERA_CAPTURED", "ALBUM_SELECTED"]
    captured_at: datetime
    uploaded_at: datetime


class ReceiptUrl(Input):
    url: str
    expires_in: int

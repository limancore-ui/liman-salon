from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BonusTransactionResponse(BaseModel):
    id: UUID
    salon_id: UUID
    customer_id: UUID
    booking_id: UUID | None
    transaction_type: str
    amount_cents: int
    balance_after_cents: int
    description: str | None
    idempotency_key: str | None
    created_by_user_id: UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BonusAdjustmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_cents: int = Field(..., description="Signed adjustment amount in cents")
    reason: str = Field(min_length=1, max_length=255)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reason must not be blank")
        return stripped

    @field_validator("amount_cents")
    @classmethod
    def non_zero_amount(cls, value: int) -> int:
        if value == 0:
            raise ValueError("amount_cents must be non-zero")
        return value

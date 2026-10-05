from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class LedgerTransactionResult:
    transaction_id: uuid.UUID
    salon_id: uuid.UUID
    customer_id: uuid.UUID
    booking_id: uuid.UUID | None
    transaction_type: str
    amount_cents: int
    balance_after_cents: int
    description: str | None
    idempotency_key: str | None
    created_at: datetime
    idempotent_replay: bool = False

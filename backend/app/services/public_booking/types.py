from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PublicBookingResult:
    booking_id: UUID
    status: str
    service_id: UUID
    staff_id: UUID
    service_start: datetime
    service_end: datetime
    hold_expires_at: datetime
    manage_token: str


@dataclass(frozen=True, slots=True)
class PublicBookingOrchestrateResult:
    salon_id: UUID
    customer_id: UUID
    booking_id: UUID
    service_start: datetime
    service_end: datetime
    hold_expires_at: datetime
    manage_token: str

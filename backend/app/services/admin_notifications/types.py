from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class AdminNotificationRow:
    id: uuid.UUID
    event_type: str
    booking_id: uuid.UUID
    created_at: datetime
    read_at: datetime | None
    booking_starts_at: datetime
    customer_name: str
    service_name: str
    staff_name: str

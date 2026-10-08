from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.services.availability.types import TimeInterval


@dataclass(frozen=True, slots=True)
class SuitableService:
    """Product-facing fields for a service that fits a gap."""

    service_id: uuid.UUID
    name: str
    duration_minutes: int
    price_cents: int
    bookable_start: datetime


@dataclass(frozen=True, slots=True)
class SmartGapEntry:
    """One free gap and active services that fit its duration and buffers."""

    gap: TimeInterval
    suitable_services: tuple[SuitableService, ...]


@dataclass(frozen=True, slots=True)
class SmartGapResult:
    """Gap-to-service matches for one staff member in a salon."""

    salon_id: uuid.UUID
    staff_id: uuid.UUID
    entries: tuple[SmartGapEntry, ...]

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.services.availability.types import ServiceForAvailability, TimeInterval


@dataclass(frozen=True, slots=True)
class SmartGapEntry:
    """One free gap and active services that fit its duration and buffers."""

    gap: TimeInterval
    suitable_services: tuple[ServiceForAvailability, ...]


@dataclass(frozen=True, slots=True)
class SmartGapResult:
    """Gap-to-service matches for one staff member in a salon."""

    salon_id: uuid.UUID
    staff_id: uuid.UUID
    entries: tuple[SmartGapEntry, ...]

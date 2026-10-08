from __future__ import annotations

from app.services.availability.intervals import gap_fits_service_net_placement
from app.services.availability.types import ServiceForAvailability, TimeInterval


def service_fits_gap(service: ServiceForAvailability, gap: TimeInterval) -> bool:
    """True when buffer + duration + buffer fits inside the gap (Availability Core rules)."""
    return gap_fits_service_net_placement(
        gap,
        duration_minutes=service.duration_minutes,
        buffer_before_minutes=service.buffer_before_minutes,
        buffer_after_minutes=service.buffer_after_minutes,
    )


def suitable_services_for_gap(
    gap: TimeInterval,
    services: tuple[ServiceForAvailability, ...],
) -> tuple[ServiceForAvailability, ...]:
    return tuple(s for s in services if service_fits_gap(s, gap))

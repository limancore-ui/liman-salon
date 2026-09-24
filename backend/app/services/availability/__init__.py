"""Availability: derive free gaps from schedule and bookings."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.availability.service import AvailabilityService

__all__ = ["AvailabilityService"]


def __getattr__(name: str) -> object:
    if name == "AvailabilityService":
        from app.services.availability.service import AvailabilityService

        return AvailabilityService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

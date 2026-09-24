"""Booking application service (create and lifecycle)."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.booking.service import BookingService

__all__ = ["BookingService"]


def __getattr__(name: str) -> object:
    if name == "BookingService":
        from app.services.booking.service import BookingService

        return BookingService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

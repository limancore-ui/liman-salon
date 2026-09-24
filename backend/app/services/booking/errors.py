from __future__ import annotations


class BookingError(Exception):
    """Base class for booking application errors."""


class BookingValidationError(BookingError):
    """Input or business rule violation before persistence."""


class BookingNotFoundError(BookingError):
    """Referenced tenant-scoped entity was not found or does not belong to the salon."""


class SlotNotAvailableError(BookingError):
    """Requested occupied interval is not within a free bookable gap."""


class BookingOverlapError(BookingError):
    """Database overlap exclusion prevented the insert (concurrent double-book)."""

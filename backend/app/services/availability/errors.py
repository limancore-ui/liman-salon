from __future__ import annotations


class AvailabilityError(Exception):
    """Base availability application error."""


class AvailabilityValidationError(AvailabilityError):
    """Invalid availability query parameters."""


class ServiceNotFoundError(AvailabilityError):
    """Service id not found in the requested salon (tenant-scoped)."""

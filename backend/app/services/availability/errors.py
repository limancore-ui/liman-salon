from __future__ import annotations


class AvailabilityError(Exception):
    """Base availability application error."""


class ServiceNotFoundError(AvailabilityError):
    """Service id not found in the requested salon (tenant-scoped)."""

from __future__ import annotations


class StaffError(Exception):
    """Base staff application error."""


class StaffValidationError(StaffError):
    """Invalid staff input."""


class StaffNotFoundError(StaffError):
    """Staff row not found for tenant scope."""

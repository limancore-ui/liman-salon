from __future__ import annotations


class ScheduleError(Exception):
    """Base schedule application error."""


class ScheduleValidationError(ScheduleError):
    """Invalid schedule input."""


class ScheduleNotFoundError(ScheduleError):
    """Schedule row or related tenant-scoped entity not found."""


class ScheduleBusyError(ScheduleError):
    """Schedule gate lock could not be acquired (contention or timeout)."""


class ImpactPreviewExpiredError(ScheduleError):
    """Echoed working-hours create preview is older than the allowed age."""


class ImpactStaleError(ScheduleError):
    """Recomputed working-hours create fingerprint does not match."""


class ImpactAckRequiredError(ScheduleError):
    """Impacts exist and the create request did not acknowledge them."""

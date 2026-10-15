from __future__ import annotations


class ScheduleError(Exception):
    """Base schedule application error."""


class ScheduleValidationError(ScheduleError):
    """Invalid schedule input."""


class ScheduleNotFoundError(ScheduleError):
    """Schedule row or related tenant-scoped entity not found."""


class ScheduleBusyError(ScheduleError):
    """Schedule gate lock could not be acquired (contention or timeout)."""

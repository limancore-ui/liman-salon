from __future__ import annotations


class ScheduleError(Exception):
    """Base schedule application error."""


class ScheduleValidationError(ScheduleError):
    """Invalid schedule input."""


class ScheduleNotFoundError(ScheduleError):
    """Schedule row or related tenant-scoped entity not found."""

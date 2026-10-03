from __future__ import annotations


class ReviewError(Exception):
    """Base class for review application errors."""


class ReviewNotFoundError(ReviewError):
    """Referenced tenant-scoped review was not found."""


class ReviewValidationError(ReviewError):
    """Input or business rule violation."""


class ReviewConflictError(ReviewError):
    """Review already exists or state conflict."""

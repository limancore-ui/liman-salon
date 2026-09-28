from __future__ import annotations


class MediaError(Exception):
    """Base media application error."""


class MediaValidationError(MediaError):
    """Invalid upload or attachment input."""


class MediaNotFoundError(MediaError):
    """Media row not found for tenant scope."""


class MediaStorageError(MediaError):
    """Storage provider failure."""


class MediaConflictError(MediaError):
    """Attachment or uniqueness conflict."""

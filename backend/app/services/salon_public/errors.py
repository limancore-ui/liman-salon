from __future__ import annotations


class SalonPublicError(Exception):
    """Base public salon entry error."""


class PublicSalonNotFoundError(SalonPublicError):
    """Salon missing or inactive for public slug lookup."""

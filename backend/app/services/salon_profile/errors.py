from __future__ import annotations


class SalonProfileError(Exception):
    """Invalid profile update."""


class SalonProfileNotFoundError(Exception):
    """Salon does not exist."""

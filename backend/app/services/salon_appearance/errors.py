from __future__ import annotations


class SalonAppearanceError(Exception):
    """Invalid appearance payload or stored document."""


class SalonAppearanceNotFoundError(Exception):
    """Salon does not exist."""

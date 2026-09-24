from __future__ import annotations


class AuthError(Exception):
    """Base authentication/authorization error."""


class InvalidCredentialsError(AuthError):
    """Login failed (generic; do not distinguish email vs password)."""


class UnauthorizedError(AuthError):
    """Missing, invalid, or expired bearer token, or inactive user."""


class SalonNotFoundError(AuthError):
    """Salon missing or inactive."""


class SalonAccessDeniedError(AuthError):
    """User lacks active membership for the salon."""


class ForbiddenRoleError(AuthError):
    """Authenticated member lacks required salon role."""

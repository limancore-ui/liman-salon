from __future__ import annotations


class CustomerError(Exception):
    """Base customer application error."""


class CustomerValidationError(CustomerError):
    """Invalid customer input."""


class CustomerNotFoundError(CustomerError):
    """Customer row not found for tenant scope."""


class CustomerConflictError(CustomerError):
    """Customer unique constraint or resolve conflict."""

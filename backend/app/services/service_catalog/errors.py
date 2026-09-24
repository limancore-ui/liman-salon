from __future__ import annotations


class ServiceCatalogError(Exception):
    """Base service catalog application error."""


class ServiceCatalogValidationError(ServiceCatalogError):
    """Invalid service catalog input."""


class ServiceCatalogNotFoundError(ServiceCatalogError):
    """Service or related tenant-scoped row not found."""

"""Service catalog administration application service."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.service_catalog.service import ServiceCatalogService

__all__ = ["ServiceCatalogService"]


def __getattr__(name: str) -> object:
    if name == "ServiceCatalogService":
        from app.services.service_catalog.service import ServiceCatalogService

        return ServiceCatalogService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

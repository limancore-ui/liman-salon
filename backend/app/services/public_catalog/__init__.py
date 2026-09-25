from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.public_catalog.service import PublicCatalogService

__all__ = ["PublicCatalogService"]


def __getattr__(name: str) -> type[PublicCatalogService]:
    if name == "PublicCatalogService":
        from app.services.public_catalog.service import PublicCatalogService

        return PublicCatalogService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

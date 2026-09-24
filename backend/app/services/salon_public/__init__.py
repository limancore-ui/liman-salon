"""Public salon entry (slug resolution) application service."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.salon_public.service import SalonPublicService

__all__ = ["SalonPublicService"]


def __getattr__(name: str) -> object:
    if name == "SalonPublicService":
        from app.services.salon_public.service import SalonPublicService

        return SalonPublicService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

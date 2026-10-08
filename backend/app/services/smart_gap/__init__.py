"""Smart Gap: match free staff gaps to fitting salon services."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.smart_gap.service import SmartGapService

__all__ = ["SmartGapService"]


def __getattr__(name: str) -> object:
    if name == "SmartGapService":
        from app.services.smart_gap.service import SmartGapService

        return SmartGapService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

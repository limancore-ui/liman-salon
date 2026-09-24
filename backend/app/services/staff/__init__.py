"""Staff administration application service."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.staff.service import StaffService

__all__ = ["StaffService"]


def __getattr__(name: str) -> object:
    if name == "StaffService":
        from app.services.staff.service import StaffService

        return StaffService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

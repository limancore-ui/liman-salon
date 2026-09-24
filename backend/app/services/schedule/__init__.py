"""Schedule administration application service."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.schedule.service import ScheduleService

__all__ = ["ScheduleService"]


def __getattr__(name: str) -> object:
    if name == "ScheduleService":
        from app.services.schedule.service import ScheduleService

        return ScheduleService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

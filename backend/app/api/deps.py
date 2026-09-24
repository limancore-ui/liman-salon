"""FastAPI dependencies for DB session and application clock."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.availability.service import AvailabilityService
from app.services.booking.service import BookingService

SessionDep = Annotated[Session, Depends(get_db)]


def get_clock() -> Callable[[], datetime]:
    """Return current UTC time; override in tests."""

    def _now() -> datetime:
        return datetime.now(timezone.utc)

    return _now


ClockDep = Annotated[Callable[[], datetime], Depends(get_clock)]


def get_as_of(clock: ClockDep) -> datetime:
    """Explicit evaluation instant for availability and booking (never client-controlled)."""

    return clock()


AsOfDep = Annotated[datetime, Depends(get_as_of)]


def get_availability_service(session: SessionDep) -> AvailabilityService:
    return AvailabilityService(session)


def get_booking_service(session: SessionDep) -> BookingService:
    return BookingService(session)


AvailabilityServiceDep = Annotated[AvailabilityService, Depends(get_availability_service)]
BookingServiceDep = Annotated[BookingService, Depends(get_booking_service)]

"""FastAPI dependencies for DB session and application clock."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.services.availability.service import AvailabilityService
from app.services.booking.service import BookingService
from app.services.public_booking.service import PublicBookingService
from app.services.schedule.service import ScheduleService
from app.services.service_catalog.service import ServiceCatalogService
from app.services.customer.service import CustomerService
from app.services.salon_public.service import SalonPublicService
from app.services.staff.service import StaffService

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


def get_public_booking_service(session: SessionDep) -> PublicBookingService:
    settings = get_settings()
    return PublicBookingService(
        session,
        public_booking_hold_seconds=settings.public_booking_hold_seconds,
    )


PublicBookingServiceDep = Annotated[
    PublicBookingService, Depends(get_public_booking_service)
]


def get_staff_service(session: SessionDep) -> StaffService:
    return StaffService(session)


StaffServiceDep = Annotated[StaffService, Depends(get_staff_service)]


def get_customer_service(session: SessionDep) -> CustomerService:
    return CustomerService(session)


CustomerServiceDep = Annotated[CustomerService, Depends(get_customer_service)]


def get_salon_public_service(session: SessionDep) -> SalonPublicService:
    return SalonPublicService(session)


SalonPublicServiceDep = Annotated[SalonPublicService, Depends(get_salon_public_service)]


def get_service_catalog_service(session: SessionDep) -> ServiceCatalogService:
    return ServiceCatalogService(session)


ServiceCatalogServiceDep = Annotated[
    ServiceCatalogService, Depends(get_service_catalog_service)
]


def get_schedule_service(session: SessionDep) -> ScheduleService:
    return ScheduleService(session)


ScheduleServiceDep = Annotated[ScheduleService, Depends(get_schedule_service)]

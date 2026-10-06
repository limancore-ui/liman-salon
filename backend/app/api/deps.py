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
from app.services.public_booking.orchestrator import PublicBookingOrchestrator
from app.services.public_booking.service import PublicBookingService
from app.services.schedule.service import ScheduleService
from app.services.salon_settings.service import SalonSettingsService
from app.services.service_catalog.service import ServiceCatalogService
from app.services.customer.service import CustomerService
from app.services.public_catalog.service import PublicCatalogService
from app.services.salon_public.service import SalonPublicService
from app.services.media.deps import build_media_service
from app.services.media.service import MediaService
from app.services.dashboard.service import DashboardService
from app.services.staff.service import StaffService
from app.services.notifications.service import NotificationService
from app.services.review.service import ReviewService
from app.services.bonus.service import BonusLedgerService
from app.services.admin_notifications.service import AdminNotificationService

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
    return BookingService(
        session,
        notifications=NotificationService(session),
        bonus_ledger=BonusLedgerService(session),
    )


AvailabilityServiceDep = Annotated[AvailabilityService, Depends(get_availability_service)]
BookingServiceDep = Annotated[BookingService, Depends(get_booking_service)]


def get_public_booking_service(session: SessionDep) -> PublicBookingService:
    settings = get_settings()
    return PublicBookingService(
        session,
        booking_manage_token_pepper=settings.booking_manage_token_pepper,
        admin_notifications=AdminNotificationService(session),
    )


def get_admin_notification_service(session: SessionDep) -> AdminNotificationService:
    return AdminNotificationService(session)


AdminNotificationServiceDep = Annotated[
    AdminNotificationService, Depends(get_admin_notification_service)
]


PublicBookingServiceDep = Annotated[
    PublicBookingService, Depends(get_public_booking_service)
]


def get_public_booking_orchestrator(
    salon_public_service: SalonPublicServiceDep,
    customer_service: CustomerServiceDep,
    public_booking_service: PublicBookingServiceDep,
) -> PublicBookingOrchestrator:
    return PublicBookingOrchestrator(
        salon_public_service=salon_public_service,
        customer_service=customer_service,
        public_booking_service=public_booking_service,
    )


PublicBookingOrchestratorDep = Annotated[
    PublicBookingOrchestrator, Depends(get_public_booking_orchestrator)
]


def get_staff_service(session: SessionDep) -> StaffService:
    return StaffService(session)


StaffServiceDep = Annotated[StaffService, Depends(get_staff_service)]


def get_dashboard_service(session: SessionDep) -> DashboardService:
    return DashboardService(session)


DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]


def get_customer_service(session: SessionDep) -> CustomerService:
    return CustomerService(session)


CustomerServiceDep = Annotated[CustomerService, Depends(get_customer_service)]


def get_salon_public_service(session: SessionDep) -> SalonPublicService:
    return SalonPublicService(session)


SalonPublicServiceDep = Annotated[SalonPublicService, Depends(get_salon_public_service)]


def get_public_catalog_service(session: SessionDep) -> PublicCatalogService:
    return PublicCatalogService(session)


PublicCatalogServiceDep = Annotated[
    PublicCatalogService, Depends(get_public_catalog_service)
]


def get_service_catalog_service(session: SessionDep) -> ServiceCatalogService:
    return ServiceCatalogService(session)


ServiceCatalogServiceDep = Annotated[
    ServiceCatalogService, Depends(get_service_catalog_service)
]


def get_schedule_service(session: SessionDep) -> ScheduleService:
    return ScheduleService(session)


ScheduleServiceDep = Annotated[ScheduleService, Depends(get_schedule_service)]


def get_media_service(session: SessionDep) -> MediaService:
    return build_media_service(session)


MediaServiceDep = Annotated[MediaService, Depends(get_media_service)]


def get_salon_settings_service(session: SessionDep) -> SalonSettingsService:
    settings = get_settings()
    return SalonSettingsService(
        session,
        app_hold_seconds=settings.public_booking_hold_seconds,
    )


SalonSettingsServiceDep = Annotated[
    SalonSettingsService, Depends(get_salon_settings_service)
]


def get_review_service(session: SessionDep) -> ReviewService:
    return ReviewService(session)


ReviewServiceDep = Annotated[ReviewService, Depends(get_review_service)]


def get_bonus_ledger_service(session: SessionDep) -> BonusLedgerService:
    return BonusLedgerService(session)


BonusLedgerServiceDep = Annotated[
    BonusLedgerService, Depends(get_bonus_ledger_service)
]

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.services.availability.errors import ServiceNotFoundError
from app.services.availability.repository import AvailabilityRepository
from app.services.availability.service import AvailabilityService
from app.services.booking.errors import SlotNotAvailableError
from app.services.booking.manage_token import generate_manage_token, hash_manage_token
from app.services.booking.service import BookingService
from app.services.admin_notifications.service import AdminNotificationService
from app.services.notifications.service import NotificationService
from app.services.public_booking.types import PublicBookingResult
from app.services.schedule.lock import acquire_schedule_lock_shared


class PublicBookingService:
    """Pre-check a public slot and create a confirmed booking through BookingService.

    The admin bell stays pending-specific. ``admin_notifications`` is accepted so
    existing callers keep a stable constructor, and this service does not enqueue
    bell events for new confirmed bookings.
    """

    def __init__(
        self,
        session: Session,
        *,
        booking_manage_token_pepper: str,
        admin_notifications: AdminNotificationService | None = None,
        notifications: NotificationService | None = None,
    ) -> None:
        self._session = session
        self._manage_token_pepper = booking_manage_token_pepper
        self._admin_notifications = admin_notifications
        self._booking = BookingService(session, notifications=notifications)
        self._availability = AvailabilityService(session)
        self._availability_repo = AvailabilityRepository(session)

    def create_public_booking(
        self,
        *,
        salon_id: uuid.UUID,
        customer_id: uuid.UUID,
        staff_id: uuid.UUID,
        service_id: uuid.UUID,
        service_start: datetime,
        as_of: datetime,
        customer_notes: str | None = None,
    ) -> PublicBookingResult:
        if service_start.tzinfo is None:
            raise ValueError("service_start must be timezone-aware")
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")

        service = self._availability_repo.get_service_for_availability(salon_id, service_id)
        if service is None:
            raise ServiceNotFoundError("service not found")

        acquire_schedule_lock_shared(self._session, salon_id)

        if service.is_active:
            if not self._availability.is_service_slot_available(
                salon_id=salon_id,
                service_id=service_id,
                staff_id=staff_id,
                service_start=service_start,
                as_of=as_of,
            ):
                raise SlotNotAvailableError("requested service slot is not available")

        manage_token = generate_manage_token()
        manage_token_hash = hash_manage_token(
            manage_token,
            pepper=self._manage_token_pepper,
        )

        result = self._booking.create_booking(
            salon_id=salon_id,
            customer_id=customer_id,
            staff_id=staff_id,
            service_id=service_id,
            requested_service_start=service_start,
            source="public",
            status="confirmed",
            as_of=as_of,
            expires_at=None,
            customer_notes=customer_notes,
            manage_token_hash=manage_token_hash,
            schedule_gate_shared_held=True,
        )

        service_end = service_start + timedelta(minutes=service.duration_minutes)

        return PublicBookingResult(
            booking_id=result.booking_id,
            status=result.status,
            service_id=service_id,
            staff_id=staff_id,
            service_start=service_start,
            service_end=service_end,
            hold_expires_at=None,
            manage_token=manage_token,
        )

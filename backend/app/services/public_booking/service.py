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
from app.services.public_booking.types import PublicBookingResult


class PublicBookingService:
    """Orchestrate public checkout holds: pre-check slot, delegate create to BookingService."""

    def __init__(
        self,
        session: Session,
        *,
        booking_manage_token_pepper: str,
        admin_notifications: AdminNotificationService | None = None,
    ) -> None:
        self._session = session
        self._manage_token_pepper = booking_manage_token_pepper
        self._admin_notifications = admin_notifications
        self._booking = BookingService(session)
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

        hold_seconds = self._booking.resolve_pending_hold_seconds(salon_id)
        hold_expires_at = as_of + timedelta(seconds=hold_seconds)

        service = self._availability_repo.get_service_for_availability(salon_id, service_id)
        if service is None:
            raise ServiceNotFoundError("service not found")

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
            status="pending",
            as_of=as_of,
            expires_at=hold_expires_at,
            customer_notes=customer_notes,
            manage_token_hash=manage_token_hash,
        )

        if self._admin_notifications is not None:
            self._admin_notifications.enqueue_public_booking_pending(
                salon_id=salon_id,
                booking_id=result.booking_id,
            )

        service_end = service_start + timedelta(minutes=service.duration_minutes)

        return PublicBookingResult(
            booking_id=result.booking_id,
            status=result.status,
            service_id=service_id,
            staff_id=staff_id,
            service_start=service_start,
            service_end=service_end,
            hold_expires_at=hold_expires_at,
            manage_token=manage_token,
        )

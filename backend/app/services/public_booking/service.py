from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.services.availability.errors import ServiceNotFoundError
from app.services.availability.repository import AvailabilityRepository
from app.services.availability.service import AvailabilityService
from app.services.booking.errors import SlotNotAvailableError
from app.services.booking.service import BookingService
from app.services.public_booking.types import PublicBookingResult


class PublicBookingService:
    """Orchestrate public checkout holds: pre-check slot, delegate create to BookingService."""

    def __init__(
        self,
        session: Session,
        *,
        public_booking_hold_seconds: int,
    ) -> None:
        self._session = session
        self._hold_seconds = public_booking_hold_seconds
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

        hold_expires_at = as_of + timedelta(seconds=self._hold_seconds)

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
        )

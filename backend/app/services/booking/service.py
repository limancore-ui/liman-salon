from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.booking import Booking
from app.services.availability.service import AvailabilityService
from app.services.booking.errors import (
    BookingNotFoundError,
    BookingOverlapError,
    BookingValidationError,
    SlotNotAvailableError,
)
from app.services.booking.repository import BookingRepository
from app.services.booking.types import (
    CreateBookingResult,
    ServiceSnapshot,
    compute_occupied_interval,
)


class BookingService:
    """Create bookings with tenant isolation, buffers, and availability checks."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = BookingRepository(session)
        self._availability = AvailabilityService(session)

    def create_booking(
        self,
        *,
        salon_id: uuid.UUID,
        customer_id: uuid.UUID,
        staff_id: uuid.UUID,
        service_id: uuid.UUID,
        requested_service_start: datetime,
        source: str,
        status: str,
        as_of: datetime,
        expires_at: datetime | None = None,
        customer_notes: str | None = None,
        internal_notes: str | None = None,
        created_by_user_id: uuid.UUID | None = None,
    ) -> CreateBookingResult:
        if as_of.tzinfo is None:
            raise BookingValidationError("as_of must be timezone-aware (UTC recommended)")
        if requested_service_start.tzinfo is None:
            raise BookingValidationError(
                "requested_service_start must be timezone-aware (UTC recommended)"
            )

        self._validate_status_and_hold(source, status, as_of, expires_at)

        with self._session.begin():
            return self._create_booking_in_transaction(
                salon_id=salon_id,
                customer_id=customer_id,
                staff_id=staff_id,
                service_id=service_id,
                requested_service_start=requested_service_start,
                source=source,
                status=status,
                as_of=as_of,
                expires_at=expires_at,
                customer_notes=customer_notes,
                internal_notes=internal_notes,
                created_by_user_id=created_by_user_id,
            )

    def _create_booking_in_transaction(
        self,
        *,
        salon_id: uuid.UUID,
        customer_id: uuid.UUID,
        staff_id: uuid.UUID,
        service_id: uuid.UUID,
        requested_service_start: datetime,
        source: str,
        status: str,
        as_of: datetime,
        expires_at: datetime | None,
        customer_notes: str | None,
        internal_notes: str | None,
        created_by_user_id: uuid.UUID | None,
    ) -> CreateBookingResult:
        currency = self._repo.get_salon_currency(salon_id)
        if currency is None:
            raise BookingNotFoundError("salon not found")

        customer = self._repo.get_customer(salon_id, customer_id)
        if customer is None:
            raise BookingNotFoundError("customer not found for salon")

        staff = self._repo.get_staff(salon_id, staff_id)
        if staff is None:
            raise BookingNotFoundError("staff not found for salon")
        if not staff.is_active or not staff.is_bookable:
            raise BookingValidationError("staff is not active or not bookable")

        service = self._repo.get_service(salon_id, service_id)
        if service is None:
            raise BookingNotFoundError("service not found for salon")
        if not service.is_active:
            raise BookingValidationError("service is not active")

        if not self._repo.staff_performs_service(salon_id, staff_id, service_id):
            raise BookingValidationError("staff does not perform this service")

        snapshot = ServiceSnapshot(
            duration_minutes=service.duration_minutes,
            buffer_before_minutes=service.buffer_before_minutes,
            buffer_after_minutes=service.buffer_after_minutes,
            price_cents=service.price_cents,
            currency_code=currency,
        )

        occupied = compute_occupied_interval(
            requested_service_start=requested_service_start,
            duration_minutes=snapshot.duration_minutes,
            buffer_before_minutes=snapshot.buffer_before_minutes,
            buffer_after_minutes=snapshot.buffer_after_minutes,
        )

        self._repo.expire_stale_pending_holds(
            salon_id=salon_id,
            staff_id=staff_id,
            window_start=occupied.occupied_start,
            window_end=occupied.occupied_end,
            as_of=as_of,
        )

        if not self._availability.is_occupied_interval_available(
            salon_id=salon_id,
            staff_id=staff_id,
            occupied_start=occupied.occupied_start,
            occupied_end=occupied.occupied_end,
            as_of=as_of,
        ):
            raise SlotNotAvailableError("no free gap for requested occupied interval")

        confirmed_at: datetime | None = None
        hold_expires_at: datetime | None = expires_at
        if status == "confirmed":
            hold_expires_at = None
            confirmed_at = as_of
        elif status == "pending":
            confirmed_at = None

        booking = Booking(
            salon_id=salon_id,
            customer_id=customer_id,
            staff_id=staff_id,
            service_id=service_id,
            starts_at=occupied.occupied_start,
            ends_at=occupied.occupied_end,
            status=status,
            source=source,
            price_cents=snapshot.price_cents,
            currency_code=snapshot.currency_code,
            duration_minutes=snapshot.duration_minutes,
            customer_notes=customer_notes,
            internal_notes=internal_notes,
            expires_at=hold_expires_at,
            confirmed_at=confirmed_at,
            created_by_user_id=created_by_user_id,
        )

        try:
            self._repo.add_booking(booking)
        except IntegrityError as exc:
            raise BookingOverlapError("booking overlaps an existing appointment") from exc

        return CreateBookingResult(
            booking_id=booking.id,
            starts_at=booking.starts_at,
            ends_at=booking.ends_at,
            status=booking.status,
        )

    @staticmethod
    def _validate_status_and_hold(
        source: str,
        status: str,
        as_of: datetime,
        expires_at: datetime | None,
    ) -> None:
        if status not in ("pending", "confirmed"):
            raise BookingValidationError(
                "create_booking supports only pending or confirmed status"
            )
        if source == "public" and status == "pending":
            if expires_at is None:
                raise BookingValidationError("public pending booking requires expires_at")
            if expires_at.tzinfo is None:
                raise BookingValidationError("expires_at must be timezone-aware")
            if expires_at <= as_of:
                raise BookingValidationError("expires_at must be after as_of for public holds")
        if status == "confirmed" and expires_at is not None:
            raise BookingValidationError("confirmed booking must not set expires_at")

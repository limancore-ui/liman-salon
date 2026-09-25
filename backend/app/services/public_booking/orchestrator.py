from __future__ import annotations

import uuid
from datetime import datetime

from app.services.customer.service import CustomerService, PublicCustomerResolveData
from app.services.public_booking.service import PublicBookingService
from app.services.public_booking.types import PublicBookingOrchestrateResult
from app.services.salon_public.service import SalonPublicService


class PublicBookingOrchestrator:
    """Slug-based public checkout: resolve salon + customer, delegate booking creation."""

    def __init__(
        self,
        salon_public_service: SalonPublicService,
        customer_service: CustomerService,
        public_booking_service: PublicBookingService,
    ) -> None:
        self._salon_public = salon_public_service
        self._customer = customer_service
        self._public_booking = public_booking_service

    def create_public_booking_by_slug(
        self,
        *,
        slug: str,
        full_name: str,
        phone: str,
        email: str | None,
        service_id: uuid.UUID,
        staff_id: uuid.UUID,
        service_start: datetime,
        as_of: datetime,
        customer_notes: str | None = None,
    ) -> PublicBookingOrchestrateResult:
        entry = self._salon_public.resolve_public_salon_by_slug(slug)
        salon_id = entry.salon_id

        customer_result = self._customer.resolve_public_customer(
            salon_id=salon_id,
            data=PublicCustomerResolveData(
                full_name=full_name,
                phone=phone,
                email=email,
            ),
        )

        booking_result = self._public_booking.create_public_booking(
            salon_id=salon_id,
            customer_id=customer_result.customer_id,
            staff_id=staff_id,
            service_id=service_id,
            service_start=service_start,
            as_of=as_of,
            customer_notes=customer_notes,
        )

        return PublicBookingOrchestrateResult(
            salon_id=salon_id,
            customer_id=customer_result.customer_id,
            booking_id=booking_result.booking_id,
            service_start=booking_result.service_start,
            service_end=booking_result.service_end,
            hold_expires_at=booking_result.hold_expires_at,
        )

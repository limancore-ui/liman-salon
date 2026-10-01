"""Notification application service (outbox enqueue + one-shot worker processing)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.booking import Booking
from app.db.models.notification import Notification
from app.services.booking.repository import BookingRepository
from app.services.notifications.constants import (
    CHANNEL_WHATSAPP,
    PROVIDER_STUB,
    TEMPLATE_BOOKING_CONFIRMED,
)
from app.services.notifications.provider import NotificationProvider, ProviderSendResult
from app.services.notifications.repository import NotificationRepository
from app.services.notifications.stub_provider import StubNotificationProvider


class NotificationService:
    def __init__(
        self,
        session: Session,
        *,
        provider: NotificationProvider | None = None,
    ) -> None:
        self._session = session
        self._repo = NotificationRepository(session)
        self._booking_repo = BookingRepository(session)
        self._provider = provider or StubNotificationProvider()

    def enqueue_booking_confirmed(
        self,
        *,
        salon_id: uuid.UUID,
        booking: Booking,
        as_of: datetime,
    ) -> Notification | None:
        """
        Enqueue WhatsApp booking_confirmed when customer has phone + whatsapp opt-in.
        No row when contact/consent missing (confirm still succeeds elsewhere).
        """
        if booking.salon_id != salon_id:
            return None

        customer = self._booking_repo.get_customer(salon_id, booking.customer_id)
        if customer is None:
            return None

        phone = (customer.phone or "").strip()
        if not phone or not customer.whatsapp_opt_in:
            return None

        existing = self._repo.get_confirm_notification(salon_id, booking.id)
        if existing is not None:
            return existing

        payload: dict[str, Any] = {
            "booking_id": str(booking.id),
            "starts_at": booking.starts_at.isoformat(),
            "customer_full_name": customer.full_name,
        }
        notification = Notification(
            salon_id=salon_id,
            booking_id=booking.id,
            customer_id=customer.id,
            channel=CHANNEL_WHATSAPP,
            template_key=TEMPLATE_BOOKING_CONFIRMED,
            recipient_address=phone,
            payload=payload,
            status="pending",
            provider=PROVIDER_STUB,
            scheduled_for=as_of,
        )
        self._repo.add(notification)
        self._session.flush()
        return notification

    def process_due_pending(self, *, as_of: datetime, batch_size: int = 50) -> int:
        """Process due pending rows once (no retry loop). Returns rows handled."""
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")

        processed = 0
        while True:
            batch = self._repo.list_due_pending_for_update(as_of=as_of, limit=batch_size)
            if not batch:
                break
            for notification in batch:
                self._deliver_one(notification, as_of=as_of)
                processed += 1
            if len(batch) < batch_size:
                break
        return processed

    def _deliver_one(self, notification: Notification, *, as_of: datetime) -> None:
        result = self._provider.send(notification=notification)
        notification.attempt_count = notification.attempt_count + 1
        self._apply_send_result(notification, result, as_of=as_of)
        self._session.flush()

    @staticmethod
    def _apply_send_result(
        notification: Notification,
        result: ProviderSendResult,
        *,
        as_of: datetime,
    ) -> None:
        if result.success:
            notification.status = "sent"
            notification.sent_at = as_of
            notification.provider_message_id = result.provider_message_id
            notification.last_error = None
        else:
            notification.status = "failed"
            notification.last_error = result.error_message or "delivery failed"

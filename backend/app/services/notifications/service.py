"""Notification application service (outbox enqueue + one-shot worker processing)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.booking import Booking
from app.db.models.notification import Notification
from app.services.booking.repository import BookingRepository
from app.services.notifications.constants import (
    BOOKING_REMINDER_LEAD,
    CHANNEL_WHATSAPP,
    MAX_DELIVERY_ATTEMPTS,
    PROVIDER_STUB,
    TEMPLATE_BOOKING_CONFIRMED,
    TEMPLATE_BOOKING_REMINDER_2H,
    retry_backoff_seconds,
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

    def enqueue_booking_reminder_2h(
        self,
        *,
        salon_id: uuid.UUID,
        booking: Booking,
    ) -> Notification | None:
        """
        Schedule WhatsApp booking_reminder_2h at NET service start minus 2 hours.

        Confirmed bookings only (callers must enforce). No row without phone + opt-in.
        """
        if booking.salon_id != salon_id or booking.status != "confirmed":
            return None

        customer = self._booking_repo.get_customer(salon_id, booking.customer_id)
        if customer is None:
            return None

        phone = (customer.phone or "").strip()
        if not phone or not customer.whatsapp_opt_in:
            return None

        scheduled_for = self._booking_reminder_scheduled_for(booking)
        if scheduled_for is None:
            return None

        existing = self._repo.get_reminder_notification(salon_id, booking.id)
        if existing is not None:
            return existing

        payload = self._booking_reminder_payload(booking, customer=customer)
        notification = Notification(
            salon_id=salon_id,
            booking_id=booking.id,
            customer_id=customer.id,
            channel=CHANNEL_WHATSAPP,
            template_key=TEMPLATE_BOOKING_REMINDER_2H,
            recipient_address=phone,
            payload=payload,
            status="pending",
            provider=PROVIDER_STUB,
            scheduled_for=scheduled_for,
        )
        self._repo.add(notification)
        self._session.flush()
        return notification

    def sync_booking_reminder_2h_after_reschedule(
        self,
        *,
        salon_id: uuid.UUID,
        booking: Booking,
    ) -> None:
        """Recalculate reminder schedule on the same outbox row (no second insert)."""
        if booking.salon_id != salon_id or booking.status != "confirmed":
            return

        existing = self._repo.get_reminder_notification(salon_id, booking.id)
        if existing is None:
            self.enqueue_booking_reminder_2h(salon_id=salon_id, booking=booking)
            return

        customer = self._booking_repo.get_customer(salon_id, booking.customer_id)
        if customer is None:
            return

        scheduled_for = self._booking_reminder_scheduled_for(booking)
        if scheduled_for is None:
            return

        existing.payload = self._booking_reminder_payload(booking, customer=customer)
        existing.scheduled_for = scheduled_for
        existing.status = "pending"
        existing.sent_at = None
        existing.provider_message_id = None
        existing.last_error = None
        existing.attempt_count = 0
        phone = (customer.phone or "").strip()
        if phone:
            existing.recipient_address = phone
        self._session.flush()

    def skip_booking_reminder_2h_on_cancel(
        self,
        *,
        salon_id: uuid.UUID,
        booking_id: uuid.UUID,
    ) -> None:
        existing = self._repo.get_reminder_notification(salon_id, booking_id)
        if existing is None or existing.status != "pending":
            return
        existing.status = "skipped"
        existing.scheduled_for = None
        self._session.flush()

    def _booking_reminder_scheduled_for(self, booking: Booking) -> datetime | None:
        net_start = self._net_service_start_for_booking(booking)
        if net_start is None:
            return None
        return net_start - BOOKING_REMINDER_LEAD

    def _net_service_start_for_booking(self, booking: Booking) -> datetime | None:
        service = self._booking_repo.get_service(booking.salon_id, booking.service_id)
        if service is None:
            return None
        return booking.starts_at + timedelta(minutes=service.buffer_before_minutes)

    def _booking_reminder_payload(self, booking: Booking, *, customer: Any) -> dict[str, Any]:
        net_start = self._net_service_start_for_booking(booking)
        service_starts_at = net_start if net_start is not None else booking.starts_at
        return {
            "booking_id": str(booking.id),
            "starts_at": service_starts_at.isoformat(),
            "customer_full_name": customer.full_name,
        }

    def process_due_pending(self, *, as_of: datetime, batch_size: int = 50) -> int:
        """
        Process due pending rows once (no in-process retry loop).

        Retries are scheduled via ``scheduled_for``; the C14 worker re-invokes this
        method on its cron interval. Provider-level exactly-once is not guaranteed:
        a timeout after the provider accepted a message may produce duplicate delivery
        on a later retry attempt.
        """
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
        if notification.attempt_count >= MAX_DELIVERY_ATTEMPTS:
            notification.status = "failed"
            notification.last_error = (
                notification.last_error or "max delivery attempts exceeded"
            )
            self._session.flush()
            return

        if notification.template_key == TEMPLATE_BOOKING_REMINDER_2H:
            if self._should_skip_reminder_at_send(notification):
                notification.status = "skipped"
                notification.scheduled_for = None
                notification.last_error = None
                self._session.flush()
                return

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
            notification.scheduled_for = None
            return

        error_message = result.error_message or "delivery failed"
        notification.last_error = error_message

        failure_kind = result.failure_kind
        if failure_kind not in ("retryable", "terminal"):
            failure_kind = "terminal"

        if (
            failure_kind == "retryable"
            and notification.attempt_count < MAX_DELIVERY_ATTEMPTS
        ):
            notification.status = "pending"
            delay_seconds = retry_backoff_seconds(
                completed_attempt_count=notification.attempt_count,
            )
            notification.scheduled_for = as_of + timedelta(seconds=delay_seconds)
            return

        notification.status = "failed"
        notification.scheduled_for = None

    def _should_skip_reminder_at_send(self, notification: Notification) -> bool:
        if notification.booking_id is None:
            return True
        booking = self._booking_repo.get_booking(
            notification.salon_id,
            notification.booking_id,
        )
        if booking is None or booking.status != "confirmed":
            return True
        if notification.customer_id is None:
            return True
        customer = self._booking_repo.get_customer(
            notification.salon_id,
            notification.customer_id,
        )
        if customer is None:
            return True
        phone = (customer.phone or "").strip()
        if not phone or not customer.whatsapp_opt_in:
            return True
        return False

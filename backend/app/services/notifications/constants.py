"""Notification channel, provider, and template identifiers."""

from __future__ import annotations

from datetime import timedelta

# WhatsApp-first confirm path (C13); delivery via stub until real provider is wired.
CHANNEL_WHATSAPP = "whatsapp"
PROVIDER_STUB = "stub"
TEMPLATE_BOOKING_CONFIRMED = "booking_confirmed"
TEMPLATE_BOOKING_REMINDER_2H = "booking_reminder_2h"

BOOKING_REMINDER_LEAD = timedelta(hours=2)

MAX_DELIVERY_ATTEMPTS = 8
BACKOFF_BASE_SECONDS = 60
BACKOFF_MAX_SECONDS = 3600


def retry_backoff_seconds(*, completed_attempt_count: int) -> int:
    """Delay after a completed attempt (attempt_count already includes that attempt)."""
    if completed_attempt_count < 1:
        raise ValueError("completed_attempt_count must be >= 1")
    exponent = completed_attempt_count - 1
    return min(BACKOFF_MAX_SECONDS, BACKOFF_BASE_SECONDS * (2**exponent))

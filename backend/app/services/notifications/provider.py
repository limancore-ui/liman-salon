"""Provider abstraction for outbound notification delivery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.db.models.notification import Notification


@dataclass(frozen=True, slots=True)
class ProviderSendResult:
    success: bool
    provider_message_id: str | None = None
    error_message: str | None = None


class NotificationProvider(Protocol):
    """Swappable delivery backend (stub, WhatsApp vendor, etc.)."""

    def send(self, *, notification: Notification) -> ProviderSendResult:
        """Attempt delivery; must not mutate persistence (service updates outbox)."""

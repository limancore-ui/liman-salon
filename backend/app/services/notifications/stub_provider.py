"""Log/no-op stub provider for local and test environments."""

from __future__ import annotations

import logging
import uuid

from app.db.models.notification import Notification
from app.services.notifications.provider import NotificationProvider, ProviderSendResult

logger = logging.getLogger(__name__)


class StubNotificationProvider:
    """Deterministic success; logs payload metadata without external I/O."""

    def send(self, *, notification: Notification) -> ProviderSendResult:
        logger.info(
            "stub notification send salon_id=%s booking_id=%s template_key=%s channel=%s recipient=%s",
            notification.salon_id,
            notification.booking_id,
            notification.template_key,
            notification.channel,
            notification.recipient_address,
        )
        return ProviderSendResult(
            success=True,
            provider_message_id=f"stub-{uuid.uuid4()}",
        )

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.salon import Salon

_SUBSCRIPTION_STATUS_CHECK = (
    "status IN ('trialing', 'active', 'past_due', 'cancelled', 'expired')"
)

_ACTIVE_SUBSCRIPTION_STATUS_WHERE = text(
    "status IN ('trialing', 'active', 'past_due')"
)


class Subscription(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Salon-level SaaS subscription (provider abstraction)."""

    __tablename__ = "subscriptions"

    salon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("salons.id", ondelete="RESTRICT"),
        nullable=False,
    )
    plan_code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="trialing",
    )
    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="manual",
    )
    provider_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default="{}",
    )

    salon: Mapped[Salon] = relationship(back_populates="subscriptions")

    __table_args__ = (
        UniqueConstraint("salon_id", "id", name="uq_subscriptions_salon_id_id"),
        CheckConstraint(
            _SUBSCRIPTION_STATUS_CHECK,
            name="ck_subscriptions_status",
        ),
        Index(
            "uq_subscriptions_provider_provider_subscription_id",
            "provider",
            "provider_subscription_id",
            unique=True,
            postgresql_where=text("provider_subscription_id IS NOT NULL"),
        ),
        Index(
            "uq_subscriptions_salon_id_active_status",
            "salon_id",
            unique=True,
            postgresql_where=_ACTIVE_SUBSCRIPTION_STATUS_WHERE,
        ),
        Index("ix_subscriptions_salon_id_status", "salon_id", "status"),
        Index(
            "ix_subscriptions_status_current_period_end",
            "status",
            "current_period_end",
        ),
    )

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CreateReviewResult:
    review_id: uuid.UUID
    booking_id: uuid.UUID
    status: str
    rating: int
    title: str | None
    body: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class BookingReviewStatusResult:
    review_id: uuid.UUID
    booking_id: uuid.UUID
    status: str
    rating: int
    title: str | None
    body: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ModerateReviewResult:
    review_id: uuid.UUID
    status: str
    moderated_at: datetime
    moderated_by_user_id: uuid.UUID
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class AdminReviewRow:
    id: uuid.UUID
    booking_id: uuid.UUID | None
    customer_display_name: str
    staff_display_name: str | None
    rating: int
    title: str | None
    body: str | None
    status: str
    created_at: datetime
    published_at: datetime | None
    moderated_at: datetime | None
    moderated_by_user_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class PublicReviewRow:
    id: uuid.UUID
    rating: int
    title: str | None
    body: str | None
    staff_display_name: str | None
    published_at: datetime
    created_at: datetime

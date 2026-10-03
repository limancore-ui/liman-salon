from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PublicBookingReviewCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, description="Manage token from booking creation")
    rating: int = Field(ge=1, le=5)
    title: str | None = Field(default=None, max_length=200)
    body: str | None = None


class PublicBookingReviewCreateResponse(BaseModel):
    review_id: UUID
    booking_id: UUID
    status: str
    rating: int
    title: str | None
    body: str | None
    created_at: datetime


class PublicBookingReviewStatusResponse(BaseModel):
    review_id: UUID
    booking_id: UUID
    status: str
    rating: int
    title: str | None
    body: str | None
    created_at: datetime


class PublicReviewOut(BaseModel):
    id: UUID
    rating: int
    title: str | None
    body: str | None
    staff_display_name: str | None
    published_at: datetime
    created_at: datetime


class PublicReviewsListResponse(BaseModel):
    salon_id: UUID
    reviews: list[PublicReviewOut]


class AdminReviewOut(BaseModel):
    id: UUID
    booking_id: UUID | None
    customer_display_name: str
    staff_display_name: str | None
    rating: int
    title: str | None
    body: str | None
    status: str
    created_at: datetime
    published_at: datetime | None
    moderated_at: datetime | None
    moderated_by_user_id: UUID | None


class AdminReviewModerationResponse(BaseModel):
    review_id: UUID
    status: str
    moderated_at: datetime
    moderated_by_user_id: UUID
    published_at: datetime | None

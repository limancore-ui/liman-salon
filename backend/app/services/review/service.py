from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.review import Review
from app.services.booking.errors import BookingNotFoundError, BookingValidationError
from app.services.booking.manage_token import verify_manage_token
from app.services.booking.repository import BookingRepository
from app.services.review.errors import (
    ReviewConflictError,
    ReviewNotFoundError,
    ReviewValidationError,
)
from app.services.review.repository import ReviewRepository
from app.services.review.types import (
    AdminReviewRow,
    BookingReviewStatusResult,
    CreateReviewResult,
    ModerateReviewResult,
    PublicReviewRow,
)

_REVIEW_ELIGIBLE_STATUS = "completed"
_TITLE_MAX = 200


class ReviewService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._reviews = ReviewRepository(session)
        self._bookings = BookingRepository(session)

    def create_review_for_booking(
        self,
        *,
        salon_id: uuid.UUID,
        booking_id: uuid.UUID,
        token: str,
        rating: int,
        title: str | None,
        body: str | None,
    ) -> CreateReviewResult:
        self._validate_rating(rating)
        title = self._normalize_optional_text(title, max_len=_TITLE_MAX, field="title")
        body = self._normalize_optional_text(body, max_len=None, field="body")

        booking = self._bookings.get_booking(salon_id, booking_id)
        if booking is None:
            raise BookingNotFoundError("booking not found")

        self._assert_manage_token(token, booking.manage_token_hash)

        if booking.status != _REVIEW_ELIGIBLE_STATUS:
            raise BookingValidationError(
                "review can only be submitted for a completed booking"
            )

        existing = self._reviews.get_review_by_booking_id(
            salon_id=salon_id,
            booking_id=booking.id,
        )
        if existing is not None:
            raise ReviewConflictError("review already exists for this booking")

        review = Review(
            salon_id=booking.salon_id,
            booking_id=booking.id,
            customer_id=booking.customer_id,
            staff_id=booking.staff_id,
            rating=rating,
            title=title,
            body=body,
            status="pending",
        )
        try:
            self._reviews.add_review(review)
        except IntegrityError as exc:
            raise ReviewConflictError(
                "review already exists for this booking"
            ) from exc

        return CreateReviewResult(
            review_id=review.id,
            booking_id=booking.id,
            status=review.status,
            rating=review.rating,
            title=review.title,
            body=review.body,
            created_at=review.created_at,
        )

    def get_booking_review_for_token(
        self,
        *,
        salon_id: uuid.UUID,
        booking_id: uuid.UUID,
        token: str,
    ) -> BookingReviewStatusResult:
        booking = self._bookings.get_booking(salon_id, booking_id)
        if booking is None:
            raise BookingNotFoundError("booking not found")

        self._assert_manage_token(token, booking.manage_token_hash)

        review = self._reviews.get_review_by_booking_id(
            salon_id=salon_id,
            booking_id=booking.id,
        )
        if review is None:
            raise ReviewNotFoundError("review not found")

        return BookingReviewStatusResult(
            review_id=review.id,
            booking_id=booking.id,
            status=review.status,
            rating=review.rating,
            title=review.title,
            body=review.body,
            created_at=review.created_at,
        )

    def list_public_published_reviews(
        self,
        *,
        salon_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PublicReviewRow]:
        if limit < 1 or limit > 200:
            raise ReviewValidationError("limit must be between 1 and 200")
        if offset < 0:
            raise ReviewValidationError("offset must be >= 0")
        return self._reviews.list_published_public(
            salon_id=salon_id,
            limit=limit,
            offset=offset,
        )

    def list_admin_reviews(
        self,
        *,
        salon_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AdminReviewRow]:
        if limit < 1 or limit > 200:
            raise ReviewValidationError("limit must be between 1 and 200")
        if offset < 0:
            raise ReviewValidationError("offset must be >= 0")
        return self._reviews.list_admin_reviews(
            salon_id=salon_id,
            limit=limit,
            offset=offset,
        )

    def publish_review(
        self,
        *,
        salon_id: uuid.UUID,
        review_id: uuid.UUID,
        moderator_user_id: uuid.UUID,
        as_of: datetime,
    ) -> ModerateReviewResult:
        return self._moderate(
            salon_id=salon_id,
            review_id=review_id,
            moderator_user_id=moderator_user_id,
            as_of=as_of,
            from_status="pending",
            to_status="published",
            set_published_at=True,
        )

    def reject_review(
        self,
        *,
        salon_id: uuid.UUID,
        review_id: uuid.UUID,
        moderator_user_id: uuid.UUID,
        as_of: datetime,
    ) -> ModerateReviewResult:
        return self._moderate(
            salon_id=salon_id,
            review_id=review_id,
            moderator_user_id=moderator_user_id,
            as_of=as_of,
            from_status="pending",
            to_status="rejected",
            set_published_at=False,
        )

    def hide_review(
        self,
        *,
        salon_id: uuid.UUID,
        review_id: uuid.UUID,
        moderator_user_id: uuid.UUID,
        as_of: datetime,
    ) -> ModerateReviewResult:
        return self._moderate(
            salon_id=salon_id,
            review_id=review_id,
            moderator_user_id=moderator_user_id,
            as_of=as_of,
            from_status="published",
            to_status="hidden",
            set_published_at=False,
        )

    def _moderate(
        self,
        *,
        salon_id: uuid.UUID,
        review_id: uuid.UUID,
        moderator_user_id: uuid.UUID,
        as_of: datetime,
        from_status: str,
        to_status: str,
        set_published_at: bool,
    ) -> ModerateReviewResult:
        if as_of.tzinfo is None:
            raise ReviewValidationError("as_of must be timezone-aware (UTC recommended)")

        review = self._reviews.get_review_by_id(salon_id=salon_id, review_id=review_id)
        if review is None:
            raise ReviewNotFoundError("review not found")

        if review.status != from_status:
            raise ReviewValidationError(
                f"review cannot transition from {review.status} to {to_status}"
            )

        review.status = to_status
        review.moderated_by_user_id = moderator_user_id
        review.moderated_at = as_of
        if set_published_at:
            review.published_at = as_of
        self._session.flush()

        return ModerateReviewResult(
            review_id=review.id,
            status=review.status,
            moderated_at=review.moderated_at,
            moderated_by_user_id=review.moderated_by_user_id,
            published_at=review.published_at,
        )

    @staticmethod
    def _assert_manage_token(raw_token: str, stored_hash: str | None) -> None:
        pepper = get_settings().booking_manage_token_pepper
        if not verify_manage_token(raw_token, stored_hash, pepper=pepper):
            raise BookingNotFoundError("booking not found")

    @staticmethod
    def _validate_rating(rating: int) -> None:
        if rating < 1 or rating > 5:
            raise ReviewValidationError("rating must be between 1 and 5")

    @staticmethod
    def _normalize_optional_text(
        value: str | None,
        *,
        max_len: int | None,
        field: str,
    ) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if trimmed == "":
            return None
        if max_len is not None and len(trimmed) > max_len:
            raise ReviewValidationError(f"{field} must be at most {max_len} characters")
        return trimmed

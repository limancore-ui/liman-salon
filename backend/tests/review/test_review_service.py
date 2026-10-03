from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.db.models.booking import Booking
from app.db.models.review import Review
from app.services.booking.errors import BookingNotFoundError, BookingValidationError
from app.services.booking.manage_token import hash_manage_token
from app.services.review.errors import ReviewConflictError, ReviewValidationError
from app.services.review.service import ReviewService

PEPPER = "test-review-pepper"
RAW_TOKEN = "valid-manage-token-for-review"
AS_OF = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
SALON_ID = uuid.uuid4()
BOOKING_ID = uuid.uuid4()
CUSTOMER_ID = uuid.uuid4()
STAFF_ID = uuid.uuid4()
MODERATOR_ID = uuid.uuid4()


@pytest.fixture(autouse=True)
def _pepper(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "booking_manage_token_pepper", PEPPER)


def _completed_booking(**overrides: object) -> Booking:
    defaults = {
        "id": BOOKING_ID,
        "salon_id": SALON_ID,
        "customer_id": CUSTOMER_ID,
        "staff_id": STAFF_ID,
        "service_id": uuid.uuid4(),
        "starts_at": AS_OF,
        "ends_at": AS_OF,
        "status": "completed",
        "price_cents": 1000,
        "currency_code": "KZT",
        "duration_minutes": 60,
        "manage_token_hash": hash_manage_token(RAW_TOKEN, pepper=PEPPER),
    }
    defaults.update(overrides)
    booking = MagicMock(spec=Booking)
    for key, value in defaults.items():
        setattr(booking, key, value)
    return booking


def test_create_review_pending_from_completed() -> None:
    session = MagicMock(spec=Session)
    svc = ReviewService(session)
    booking = _completed_booking()
    svc._bookings.get_booking = MagicMock(return_value=booking)  # type: ignore[method-assign]
    svc._reviews.get_review_by_booking_id = MagicMock(return_value=None)  # type: ignore[method-assign]

    captured: dict[str, Review] = {}

    def _add(review: Review) -> Review:
        review.id = uuid.uuid4()
        review.created_at = AS_OF
        captured["review"] = review
        return review

    svc._reviews.add_review = MagicMock(side_effect=_add)  # type: ignore[method-assign]

    result = svc.create_review_for_booking(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        token=RAW_TOKEN,
        rating=4,
        title="Nice",
        body="Thanks",
    )
    assert result.status == "pending"
    assert result.rating == 4
    review = captured["review"]
    assert review.salon_id == SALON_ID
    assert review.customer_id == CUSTOMER_ID
    assert review.staff_id == STAFF_ID
    assert review.booking_id == BOOKING_ID


@pytest.mark.parametrize(
    "status",
    ["pending", "confirmed", "in_progress", "cancelled", "no_show", "expired"],
)
def test_create_review_rejects_non_completed(status: str) -> None:
    session = MagicMock(spec=Session)
    svc = ReviewService(session)
    svc._bookings.get_booking = MagicMock(  # type: ignore[method-assign]
        return_value=_completed_booking(status=status)
    )
    with pytest.raises(BookingValidationError, match="completed"):
        svc.create_review_for_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token=RAW_TOKEN,
            rating=5,
            title=None,
            body=None,
        )


def test_create_review_invalid_token() -> None:
    session = MagicMock(spec=Session)
    svc = ReviewService(session)
    svc._bookings.get_booking = MagicMock(return_value=_completed_booking())  # type: ignore[method-assign]
    with pytest.raises(BookingNotFoundError):
        svc.create_review_for_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token="wrong",
            rating=5,
            title=None,
            body=None,
        )


def test_create_review_duplicate() -> None:
    session = MagicMock(spec=Session)
    svc = ReviewService(session)
    svc._bookings.get_booking = MagicMock(return_value=_completed_booking())  # type: ignore[method-assign]
    svc._reviews.get_review_by_booking_id = MagicMock(  # type: ignore[method-assign]
        return_value=MagicMock(spec=Review)
    )
    with pytest.raises(ReviewConflictError):
        svc.create_review_for_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token=RAW_TOKEN,
            rating=5,
            title=None,
            body=None,
        )


def test_moderation_transitions_and_metadata() -> None:
    session = MagicMock(spec=Session)
    svc = ReviewService(session)
    review = Review(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        customer_id=CUSTOMER_ID,
        staff_id=STAFF_ID,
        rating=5,
        status="pending",
    )
    review.id = uuid.uuid4()
    svc._reviews.get_review_by_id = MagicMock(return_value=review)  # type: ignore[method-assign]

    published = svc.publish_review(
        salon_id=SALON_ID,
        review_id=review.id,
        moderator_user_id=MODERATOR_ID,
        as_of=AS_OF,
    )
    assert published.status == "published"
    assert review.published_at == AS_OF
    assert review.moderated_by_user_id == MODERATOR_ID

    review.status = "published"
    hidden = svc.hide_review(
        salon_id=SALON_ID,
        review_id=review.id,
        moderator_user_id=MODERATOR_ID,
        as_of=AS_OF,
    )
    assert hidden.status == "hidden"


def test_hide_rejects_from_pending() -> None:
    session = MagicMock(spec=Session)
    svc = ReviewService(session)
    review = Review(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        customer_id=CUSTOMER_ID,
        staff_id=STAFF_ID,
        rating=3,
        status="pending",
    )
    review.id = uuid.uuid4()
    svc._reviews.get_review_by_id = MagicMock(return_value=review)  # type: ignore[method-assign]
    with pytest.raises(ReviewValidationError, match="transition"):
        svc.hide_review(
            salon_id=SALON_ID,
            review_id=review.id,
            moderator_user_id=MODERATOR_ID,
            as_of=AS_OF,
        )

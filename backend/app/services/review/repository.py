from __future__ import annotations

import uuid

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models.customer import Customer
from app.db.models.review import Review
from app.db.models.staff import Staff
from app.services.review.types import AdminReviewRow, PublicReviewRow


class ReviewRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_review_by_id(
        self, *, salon_id: uuid.UUID, review_id: uuid.UUID
    ) -> Review | None:
        return self._session.scalar(
            select(Review).where(
                Review.salon_id == salon_id,
                Review.id == review_id,
            )
        )

    def get_review_by_booking_id(
        self, *, salon_id: uuid.UUID, booking_id: uuid.UUID
    ) -> Review | None:
        return self._session.scalar(
            select(Review).where(
                Review.salon_id == salon_id,
                Review.booking_id == booking_id,
            )
        )

    def add_review(self, review: Review) -> Review:
        self._session.add(review)
        self._session.flush()
        return review

    def list_admin_reviews(
        self,
        *,
        salon_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AdminReviewRow]:
        stmt = (
            select(
                Review,
                Customer.full_name,
                Staff.display_name,
            )
            .join(
                Customer,
                (Customer.salon_id == Review.salon_id)
                & (Customer.id == Review.customer_id),
            )
            .outerjoin(
                Staff,
                (Staff.salon_id == Review.salon_id) & (Staff.id == Review.staff_id),
            )
            .where(Review.salon_id == salon_id)
            .order_by(desc(Review.created_at), Review.id)
            .limit(limit)
            .offset(offset)
        )
        rows: list[AdminReviewRow] = []
        for review, customer_name, staff_name in self._session.execute(stmt).all():
            rows.append(
                AdminReviewRow(
                    id=review.id,
                    booking_id=review.booking_id,
                    customer_display_name=customer_name,
                    staff_display_name=staff_name,
                    rating=review.rating,
                    title=review.title,
                    body=review.body,
                    status=review.status,
                    created_at=review.created_at,
                    published_at=review.published_at,
                    moderated_at=review.moderated_at,
                    moderated_by_user_id=review.moderated_by_user_id,
                )
            )
        return rows

    def list_published_public(
        self,
        *,
        salon_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PublicReviewRow]:
        stmt = (
            select(
                Review,
                Staff.display_name,
            )
            .outerjoin(
                Staff,
                (Staff.salon_id == Review.salon_id) & (Staff.id == Review.staff_id),
            )
            .where(
                Review.salon_id == salon_id,
                Review.status == "published",
            )
            .order_by(desc(Review.published_at), Review.id)
            .limit(limit)
            .offset(offset)
        )
        rows: list[PublicReviewRow] = []
        for review, staff_name in self._session.execute(stmt).all():
            if review.published_at is None:
                continue
            rows.append(
                PublicReviewRow(
                    id=review.id,
                    rating=review.rating,
                    title=review.title,
                    body=review.body,
                    staff_display_name=staff_name,
                    published_at=review.published_at,
                    created_at=review.created_at,
                )
            )
        return rows

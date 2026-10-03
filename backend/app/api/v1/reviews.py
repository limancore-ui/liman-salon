from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import AsOfDep, ReviewServiceDep
from app.api.schemas.review import (
    AdminReviewModerationResponse,
    AdminReviewOut,
)
from app.auth.deps import require_roles
from app.auth.principals import SalonContext

router = APIRouter(prefix="/salons/{salon_id}/reviews", tags=["reviews"])

WriteSalonContext = Annotated[
    SalonContext,
    Depends(require_roles("owner", "admin")),
]


def _assert_path_salon(context: SalonContext, salon_id: uuid.UUID) -> None:
    if context.salon_id != salon_id:
        raise RuntimeError("salon_id path mismatch with SalonContext")


@router.get("", response_model=list[AdminReviewOut])
def list_admin_reviews(
    salon_id: uuid.UUID,
    context: WriteSalonContext,
    review_service: ReviewServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AdminReviewOut]:
    _assert_path_salon(context, salon_id)
    rows = review_service.list_admin_reviews(
        salon_id=context.salon_id,
        limit=limit,
        offset=offset,
    )
    return [
        AdminReviewOut(
            id=row.id,
            booking_id=row.booking_id,
            customer_display_name=row.customer_display_name,
            staff_display_name=row.staff_display_name,
            rating=row.rating,
            title=row.title,
            body=row.body,
            status=row.status,
            created_at=row.created_at,
            published_at=row.published_at,
            moderated_at=row.moderated_at,
            moderated_by_user_id=row.moderated_by_user_id,
        )
        for row in rows
    ]


@router.post(
    "/{review_id}/publish",
    response_model=AdminReviewModerationResponse,
    status_code=200,
)
def publish_review(
    salon_id: uuid.UUID,
    review_id: uuid.UUID,
    context: WriteSalonContext,
    review_service: ReviewServiceDep,
    as_of: AsOfDep,
) -> AdminReviewModerationResponse:
    _assert_path_salon(context, salon_id)
    result = review_service.publish_review(
        salon_id=context.salon_id,
        review_id=review_id,
        moderator_user_id=context.user_id,
        as_of=as_of,
    )
    return AdminReviewModerationResponse(
        review_id=result.review_id,
        status=result.status,
        moderated_at=result.moderated_at,
        moderated_by_user_id=result.moderated_by_user_id,
        published_at=result.published_at,
    )


@router.post(
    "/{review_id}/reject",
    response_model=AdminReviewModerationResponse,
    status_code=200,
)
def reject_review(
    salon_id: uuid.UUID,
    review_id: uuid.UUID,
    context: WriteSalonContext,
    review_service: ReviewServiceDep,
    as_of: AsOfDep,
) -> AdminReviewModerationResponse:
    _assert_path_salon(context, salon_id)
    result = review_service.reject_review(
        salon_id=context.salon_id,
        review_id=review_id,
        moderator_user_id=context.user_id,
        as_of=as_of,
    )
    return AdminReviewModerationResponse(
        review_id=result.review_id,
        status=result.status,
        moderated_at=result.moderated_at,
        moderated_by_user_id=result.moderated_by_user_id,
        published_at=result.published_at,
    )


@router.post(
    "/{review_id}/hide",
    response_model=AdminReviewModerationResponse,
    status_code=200,
)
def hide_review(
    salon_id: uuid.UUID,
    review_id: uuid.UUID,
    context: WriteSalonContext,
    review_service: ReviewServiceDep,
    as_of: AsOfDep,
) -> AdminReviewModerationResponse:
    _assert_path_salon(context, salon_id)
    result = review_service.hide_review(
        salon_id=context.salon_id,
        review_id=review_id,
        moderator_user_id=context.user_id,
        as_of=as_of,
    )
    return AdminReviewModerationResponse(
        review_id=result.review_id,
        status=result.status,
        moderated_at=result.moderated_at,
        moderated_by_user_id=result.moderated_by_user_id,
        published_at=result.published_at,
    )

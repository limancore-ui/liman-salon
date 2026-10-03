from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_as_of, get_review_service
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.review.errors import ReviewNotFoundError, ReviewValidationError
from app.services.review.service import ReviewService
from app.services.review.types import AdminReviewRow, ModerateReviewResult

from tests.api.conftest import FIXED_AS_OF

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
REVIEW_ID = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
NOW = datetime.now(timezone.utc)
MOD_AT = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _auth_app(
    *,
    role: str = "owner",
    salon_id: uuid.UUID = SALON_A,
) -> tuple[TestClient, MagicMock, dict[str, str]]:
    app = create_app()
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="owner@example.com",
        full_name="Owner",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=salon_id,
        name="Salon",
        slug="salon",
        is_active=True,
        timezone="UTC",
        currency_code="KZT",
    )
    mock_auth.get_active_membership.return_value = SimpleNamespace(
        salon_id=salon_id,
        user_id=USER_ID,
        role=role,
        is_active=True,
    )
    mock_review = MagicMock(spec=ReviewService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_review_service] = lambda: mock_review
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, mock_review, headers


def _moderate_result() -> ModerateReviewResult:
    return ModerateReviewResult(
        review_id=REVIEW_ID,
        status="published",
        moderated_at=MOD_AT,
        moderated_by_user_id=USER_ID,
        published_at=MOD_AT,
    )


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_admin_list_reviews_owner_admin(role: str) -> None:
    client, mock_review, headers = _auth_app(role=role)
    mock_review.list_admin_reviews.return_value = [
        AdminReviewRow(
            id=REVIEW_ID,
            booking_id=uuid.uuid4(),
            customer_display_name="Guest",
            staff_display_name="Stylist",
            rating=5,
            title=None,
            body="Great",
            status="pending",
            created_at=NOW,
            published_at=None,
            moderated_at=None,
            moderated_by_user_id=None,
        )
    ]
    response = client.get(f"/api/v1/salons/{SALON_A}/reviews", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    mock_review.list_admin_reviews.assert_called_once_with(
        salon_id=SALON_A,
        limit=50,
        offset=0,
    )


@pytest.mark.parametrize("role", ["staff", "receptionist"])
def test_admin_list_reviews_forbidden(role: str) -> None:
    client, _mock_review, headers = _auth_app(role=role)
    response = client.get(f"/api/v1/salons/{SALON_A}/reviews", headers=headers)
    assert response.status_code == 403


@pytest.mark.parametrize(
    "action,method_name",
    [
        ("publish", "publish_review"),
        ("reject", "reject_review"),
        ("hide", "hide_review"),
    ],
)
@pytest.mark.parametrize("role", ["owner", "admin"])
def test_admin_moderation_owner_admin(
    action: str, method_name: str, role: str
) -> None:
    client, mock_review, headers = _auth_app(role=role)
    getattr(mock_review, method_name).return_value = _moderate_result()
    response = client.post(
        f"/api/v1/salons/{SALON_A}/reviews/{REVIEW_ID}/{action}",
        headers=headers,
    )
    assert response.status_code == 200
    getattr(mock_review, method_name).assert_called_once()


def test_admin_publish_not_found() -> None:
    client, mock_review, headers = _auth_app()
    mock_review.publish_review.side_effect = ReviewNotFoundError("review not found")
    response = client.post(
        f"/api/v1/salons/{SALON_A}/reviews/{REVIEW_ID}/publish",
        headers=headers,
    )
    assert response.status_code == 404


def test_admin_publish_invalid_transition() -> None:
    client, mock_review, headers = _auth_app()
    mock_review.publish_review.side_effect = ReviewValidationError(
        "review cannot transition from published to published"
    )
    response = client.post(
        f"/api/v1/salons/{SALON_A}/reviews/{REVIEW_ID}/publish",
        headers=headers,
    )
    assert response.status_code == 422


def test_admin_list_unauthenticated() -> None:
    app = create_app()
    with TestClient(app) as client:
        assert client.get(f"/api/v1/salons/{SALON_A}/reviews").status_code == 401

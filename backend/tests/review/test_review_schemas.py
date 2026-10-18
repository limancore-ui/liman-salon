from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.schemas.review import PublicBookingReviewCreateRequest


def _request(*, body: str | None, title: str | None = None):
    return PublicBookingReviewCreateRequest.model_validate(
        {
            "token": "synthetic-manage-token",
            "rating": 5,
            "title": title,
            "body": body,
        }
    )


def test_review_request_accepts_body_at_1000_characters() -> None:
    request = _request(body="x" * 1000)

    assert request.body == "x" * 1000


def test_review_request_rejects_body_at_1001_characters() -> None:
    with pytest.raises(ValidationError):
        _request(body="x" * 1001)


@pytest.mark.parametrize("body", [None, "", "   ", " \t "])
def test_review_request_preserves_empty_and_whitespace_values(
    body: str | None,
) -> None:
    assert _request(body=body).body == body


def test_review_request_keeps_title_limit_at_200_characters() -> None:
    assert _request(body=None, title="t" * 200).title == "t" * 200

    with pytest.raises(ValidationError):
        _request(body=None, title="t" * 201)

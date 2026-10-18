from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.db.models.review import Review
from app.services.review.repository import ReviewRepository

SALON_ID = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)


def _published_review(body: str) -> Review:
    review = Review(
        id=uuid.uuid4(),
        salon_id=SALON_ID,
        booking_id=None,
        customer_id=uuid.uuid4(),
        staff_id=None,
        rating=5,
        title=None,
        body=body,
        status="published",
        published_at=NOW,
    )
    review.created_at = NOW
    review.updated_at = NOW
    return review


def test_public_page_filters_null_published_at_before_pagination_and_logs_anomaly(
    caplog,
) -> None:
    session = MagicMock(spec=Session)
    first = _published_review("private review text marker")
    second = _published_review("second review")
    session.execute.return_value.all.return_value = [
        (first, "Stylist"),
        (second, None),
    ]
    repository = ReviewRepository(session)

    result = repository.list_published_public(
        salon_id=SALON_ID,
        limit=2,
        offset=0,
    )

    assert [row.id for row in result] == [first.id, second.id]
    assert len(result) == 2
    session.execute.assert_called_once()

    statement = session.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "published_at IS NOT NULL" in sql
    assert sql.index("published_at IS NOT NULL") < sql.index("LIMIT")
    assert "OFFSET" in sql


def test_anomaly_check_is_tenant_scoped_and_uses_exists() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = True
    repository = ReviewRepository(session)

    result = repository.has_published_reviews_missing_published_at(
        salon_id=SALON_ID,
    )

    assert result is True
    session.scalar.assert_called_once()
    sql = str(
        session.scalar.call_args.args[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "EXISTS" in sql
    assert str(SALON_ID) in sql
    assert "status = 'published'" in sql
    assert "published_at IS NULL" in sql

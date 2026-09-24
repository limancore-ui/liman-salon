from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID

from app.api.deps import get_as_of, get_availability_service
from app.main import create_app
from app.services.availability.types import TimeInterval
from fastapi.testclient import TestClient

from tests.api.conftest import FIXED_AS_OF, SALON_ID, STAFF_ID


def test_availability_returns_gaps() -> None:
    app = create_app()
    mock_service = MagicMock()
    start = datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc)
    mock_service.get_free_gaps.return_value = [TimeInterval(start=start, end=end)]

    app.dependency_overrides[get_availability_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/salons/{SALON_ID}/availability",
            params={
                "staff_id": str(STAFF_ID),
                "start_date": "2026-09-25",
                "end_date": "2026-09-25",
                "service_duration_minutes": 60,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["gaps"]) == 1
    assert data["gaps"][0]["start"] == start.isoformat().replace("+00:00", "Z")

    mock_service.get_free_gaps.assert_called_once_with(
        salon_id=SALON_ID,
        staff_id=STAFF_ID,
        start_date=date(2026, 9, 25),
        end_date=date(2026, 9, 25),
        service_duration_minutes=60,
        as_of=FIXED_AS_OF,
    )


def test_availability_invalid_duration_returns_422(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/salons/{SALON_ID}/availability",
        params={
            "staff_id": str(STAFF_ID),
            "start_date": "2026-09-25",
            "end_date": "2026-09-25",
            "service_duration_minutes": 0,
        },
    )
    assert response.status_code == 422


def test_client_cannot_set_as_of(client: TestClient) -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.get_free_gaps.return_value = []
    app.dependency_overrides[get_availability_service] = lambda: mock_service

    fake_as_of = datetime(2020, 1, 1, tzinfo=timezone.utc)
    app.dependency_overrides[get_as_of] = lambda: fake_as_of

    with TestClient(app) as c:
        c.get(
            f"/api/v1/salons/{SALON_ID}/availability",
            params={
                "staff_id": str(STAFF_ID),
                "start_date": "2026-09-25",
                "end_date": "2026-09-25",
                "service_duration_minutes": 30,
                "as_of": "2020-01-01T00:00:00Z",
            },
        )
        mock_service.get_free_gaps.assert_called_once()
        assert mock_service.get_free_gaps.call_args.kwargs["as_of"] == fake_as_of

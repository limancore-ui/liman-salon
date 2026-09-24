from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from app.api.deps import get_as_of, get_availability_service
from app.main import create_app
from app.services.availability.errors import ServiceNotFoundError
from app.services.availability.types import (
    ServiceAvailabilityResult,
    ServiceAvailabilitySlot,
    StaffServiceAvailability,
)
from fastapi.testclient import TestClient

from tests.api.conftest import FIXED_AS_OF, SALON_ID

SERVICE_ID = uuid4()
STAFF_ID = uuid4()


def test_service_availability_returns_net_slots() -> None:
    app = create_app()
    mock_service = MagicMock()
    slot_start = datetime(2026, 9, 25, 9, 15, tzinfo=timezone.utc)
    slot_end = datetime(2026, 9, 25, 16, 45, tzinfo=timezone.utc)
    mock_service.get_service_availability.return_value = ServiceAvailabilityResult(
        service_id=SERVICE_ID,
        staff=(
            StaffServiceAvailability(
                staff_id=STAFF_ID,
                slots=(
                    ServiceAvailabilitySlot(
                        service_start=slot_start,
                        service_end=slot_end,
                    ),
                ),
            ),
        ),
    )
    app.dependency_overrides[get_availability_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/salons/{SALON_ID}/availability/service",
            params={
                "service_id": str(SERVICE_ID),
                "start_date": "2026-09-25",
                "end_date": "2026-09-25",
                "staff_id": str(STAFF_ID),
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["service_id"] == str(SERVICE_ID)
    assert len(data["staff"]) == 1
    assert data["staff"][0]["staff_id"] == str(STAFF_ID)
    assert data["staff"][0]["slots"][0]["service_start"] == slot_start.isoformat().replace(
        "+00:00", "Z"
    )

    mock_service.get_service_availability.assert_called_once_with(
        salon_id=SALON_ID,
        service_id=SERVICE_ID,
        start_date=date(2026, 9, 25),
        end_date=date(2026, 9, 25),
        staff_id=STAFF_ID,
        as_of=FIXED_AS_OF,
    )


def test_service_availability_client_cannot_set_as_of() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.get_service_availability.return_value = ServiceAvailabilityResult(
        service_id=SERVICE_ID,
        staff=(),
    )
    app.dependency_overrides[get_availability_service] = lambda: mock_service
    fake_as_of = datetime(2020, 1, 1, tzinfo=timezone.utc)
    app.dependency_overrides[get_as_of] = lambda: fake_as_of

    with TestClient(app) as client:
        client.get(
            f"/api/v1/salons/{SALON_ID}/availability/service",
            params={
                "service_id": str(SERVICE_ID),
                "start_date": "2026-09-25",
                "end_date": "2026-09-25",
                "as_of": "2020-01-01T00:00:00Z",
            },
        )

    assert mock_service.get_service_availability.call_args.kwargs["as_of"] == fake_as_of


def test_service_availability_missing_service_404() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.get_service_availability.side_effect = ServiceNotFoundError(
        "service not found"
    )
    app.dependency_overrides[get_availability_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/salons/{SALON_ID}/availability/service",
            params={
                "service_id": str(SERVICE_ID),
                "start_date": "2026-09-25",
                "end_date": "2026-09-25",
            },
        )

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_service_availability_inactive_service_200_empty() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.get_service_availability.return_value = ServiceAvailabilityResult(
        service_id=SERVICE_ID,
        staff=(),
    )
    app.dependency_overrides[get_availability_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/salons/{SALON_ID}/availability/service",
            params={
                "service_id": str(SERVICE_ID),
                "start_date": "2026-09-25",
                "end_date": "2026-09-25",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["service_id"] == str(SERVICE_ID)
    assert data["staff"] == []


def test_service_availability_no_auth_required(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/salons/{SALON_ID}/availability/service",
        params={
            "service_id": str(SERVICE_ID),
            "start_date": "2026-09-25",
            "end_date": "2026-09-25",
        },
    )
    assert response.status_code != 401

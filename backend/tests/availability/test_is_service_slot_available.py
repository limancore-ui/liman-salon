from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.availability.errors import ServiceNotFoundError
from app.services.availability.service import AvailabilityService
from app.services.availability.types import ServiceForAvailability

UTC = timezone.utc
SALON_ID = uuid.uuid4()
STAFF_ID = uuid.uuid4()
SERVICE_ID = uuid.uuid4()
AS_OF = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
SERVICE_START = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)


def _service_with_repo(repo: MagicMock) -> AvailabilityService:
    session = MagicMock()
    svc = AvailabilityService(session)
    svc._repo = repo
    return svc


def test_is_service_slot_available_missing_raises() -> None:
    repo = MagicMock()
    repo.get_service_for_availability.return_value = None
    svc = _service_with_repo(repo)

    with pytest.raises(ServiceNotFoundError):
        svc.is_service_slot_available(
            salon_id=SALON_ID,
            service_id=SERVICE_ID,
            staff_id=STAFF_ID,
            service_start=SERVICE_START,
            as_of=AS_OF,
        )


def test_is_service_slot_available_inactive_false() -> None:
    repo = MagicMock()
    repo.get_service_for_availability.return_value = ServiceForAvailability(
        id=SERVICE_ID,
        is_active=False,
        duration_minutes=30,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
    )
    svc = _service_with_repo(repo)

    assert not svc.is_service_slot_available(
        salon_id=SALON_ID,
        service_id=SERVICE_ID,
        staff_id=STAFF_ID,
        service_start=SERVICE_START,
        as_of=AS_OF,
    )
    repo.staff_eligible_for_service.assert_not_called()


def test_is_service_slot_available_delegates_occupied_check() -> None:
    repo = MagicMock()
    repo.get_service_for_availability.return_value = ServiceForAvailability(
        id=SERVICE_ID,
        is_active=True,
        duration_minutes=60,
        buffer_before_minutes=10,
        buffer_after_minutes=5,
    )
    repo.staff_eligible_for_service.return_value = True
    svc = _service_with_repo(repo)

    with patch.object(svc, "is_occupied_interval_available", return_value=True) as occupied:
        ok = svc.is_service_slot_available(
            salon_id=SALON_ID,
            service_id=SERVICE_ID,
            staff_id=STAFF_ID,
            service_start=SERVICE_START,
            as_of=AS_OF,
        )

    assert ok is True
    occupied.assert_called_once()
    kwargs = occupied.call_args.kwargs
    assert kwargs["salon_id"] == SALON_ID
    assert kwargs["staff_id"] == STAFF_ID
    assert kwargs["occupied_start"] == SERVICE_START - timedelta(minutes=10)
    assert kwargs["occupied_end"] == SERVICE_START + timedelta(minutes=65)

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_as_of, get_availability_service, get_booking_service, get_clock
from app.main import create_app

SALON_ID = UUID("11111111-1111-4111-8111-111111111111")
STAFF_ID = UUID("22222222-2222-4222-8222-222222222222")
FIXED_AS_OF = datetime(2026, 9, 24, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def fixed_clock() -> datetime:
    return FIXED_AS_OF


@pytest.fixture
def client(fixed_clock: datetime) -> TestClient:
    app = create_app()

    app.dependency_overrides[get_clock] = lambda: (lambda: fixed_clock)
    app.dependency_overrides[get_as_of] = lambda: fixed_clock

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def salon_id() -> UUID:
    return SALON_ID


@pytest.fixture
def new_uuid() -> UUID:
    return uuid4()

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_as_of, get_public_catalog_service
from app.main import create_app
from app.services.availability.errors import AvailabilityValidationError
from app.services.public_catalog.service import PublicCatalogService
from app.services.salon_public.types import PublicSalonEntry

SALON_A = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
SERVICE_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
SLUG = "demo"
FIXED_AS_OF = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _entry() -> PublicSalonEntry:
    return PublicSalonEntry(
        salon_id=SALON_A,
        slug=SLUG,
        name="Demo",
        currency_code="KZT",
        timezone="UTC",
    )


@patch.object(PublicCatalogService, "__init__", lambda self, session: None)
def test_one_day_public_availability_range_allowed() -> None:
    svc = PublicCatalogService(MagicMock())
    svc._salon_public = MagicMock()
    svc._availability = MagicMock()
    svc._salon_public.resolve_public_salon_by_slug.return_value = _entry()
    day = date(2026, 1, 10)

    svc.get_service_availability_by_slug(
        slug=SLUG,
        service_id=SERVICE_ID,
        start_date=day,
        end_date=day,
        as_of=FIXED_AS_OF,
    )

    svc._availability.get_service_availability.assert_called_once()


@patch.object(PublicCatalogService, "__init__", lambda self, session: None)
def test_exactly_62_inclusive_calendar_days_allowed() -> None:
    svc = PublicCatalogService(MagicMock())
    svc._salon_public = MagicMock()
    svc._availability = MagicMock()
    svc._salon_public.resolve_public_salon_by_slug.return_value = _entry()
    start = date(2026, 1, 1)
    end = date(2026, 3, 3)

    svc.get_service_availability_by_slug(
        slug=SLUG,
        service_id=SERVICE_ID,
        start_date=start,
        end_date=end,
        as_of=FIXED_AS_OF,
    )

    assert (end - start).days + 1 == 62
    svc._availability.get_service_availability.assert_called_once()


@patch.object(PublicCatalogService, "__init__", lambda self, session: None)
def test_over_62_calendar_days_rejected_before_engine() -> None:
    svc = PublicCatalogService(MagicMock())
    svc._salon_public = MagicMock()
    svc._availability = MagicMock()
    svc._salon_public.resolve_public_salon_by_slug.return_value = _entry()
    start = date(2026, 1, 1)
    end = date(2026, 3, 4)

    with pytest.raises(AvailabilityValidationError, match="62"):
        svc.get_service_availability_by_slug(
            slug=SLUG,
            service_id=SERVICE_ID,
            start_date=start,
            end_date=end,
            as_of=FIXED_AS_OF,
        )

    svc._availability.get_service_availability.assert_not_called()


@patch.object(PublicCatalogService, "__init__", lambda self, session: None)
def test_public_slug_availability_date_range_over_limit_422() -> None:
    catalog = PublicCatalogService(MagicMock())
    catalog._salon_public = MagicMock()
    catalog._availability = MagicMock()
    catalog._salon_public.resolve_public_salon_by_slug.return_value = _entry()

    app = create_app()
    app.dependency_overrides[get_public_catalog_service] = lambda: catalog
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/public/salons/{SLUG}/availability/service",
            params={
                "service_id": str(SERVICE_ID),
                "start_date": "2026-01-01",
                "end_date": "2026-03-04",
            },
        )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    catalog._availability.get_service_availability.assert_not_called()

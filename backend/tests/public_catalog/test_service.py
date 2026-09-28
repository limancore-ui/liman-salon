from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.db.models.service import Service
from app.services.public_catalog.service import PublicCatalogService
from app.services.salon_public.types import PublicSalonEntry
from app.services.service_catalog.errors import ServiceCatalogNotFoundError

SALON_A = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
SALON_B = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SERVICE_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
STAFF_ASSIGNED = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
STAFF_UNASSIGNED = uuid.UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")


def _entry(salon_id: uuid.UUID = SALON_A) -> PublicSalonEntry:
    return PublicSalonEntry(
        salon_id=salon_id,
        slug="demo",
        name="Demo",
        currency_code="KZT",
        timezone="Asia/Almaty",
    )


def _service(*, active: bool = True, sort_order: int = 0, name: str = "Cut") -> Service:
    return Service(
        id=SERVICE_ID,
        salon_id=SALON_A,
        name=name,
        description=None,
        duration_minutes=30,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        price_cents=1000,
        is_active=active,
        sort_order=sort_order,
    )


@patch.object(PublicCatalogService, "__init__", lambda self, session: None)
def test_list_active_services_excludes_inactive_via_catalog_flag() -> None:
    svc = PublicCatalogService(MagicMock())
    svc._salon_public = MagicMock()
    svc._catalog = MagicMock()
    svc._media_repo = MagicMock()
    svc._media_repo.resolve_attached_media_id.return_value = None
    svc._salon_public.resolve_public_salon_by_slug.return_value = _entry()
    active = _service(active=True)
    svc._catalog.list_services.return_value = [active]

    result = svc.list_active_services_by_slug("demo")

    svc._catalog.list_services.assert_called_once_with(salon_id=SALON_A, active_only=True)
    assert len(result.services) == 1
    assert result.services[0].id == SERVICE_ID


@patch.object(PublicCatalogService, "__init__", lambda self, session: None)
def test_list_active_services_tenant_scoped_to_resolved_salon() -> None:
    svc = PublicCatalogService(MagicMock())
    svc._salon_public = MagicMock()
    svc._catalog = MagicMock()
    svc._salon_public.resolve_public_salon_by_slug.return_value = _entry(salon_id=SALON_B)
    svc._catalog.list_services.return_value = []

    svc.list_active_services_by_slug("other-salon")

    svc._catalog.list_services.assert_called_once_with(salon_id=SALON_B, active_only=True)


@patch.object(PublicCatalogService, "__init__", lambda self, session: None)
def test_list_active_services_preserves_catalog_order() -> None:
    svc = PublicCatalogService(MagicMock())
    svc._salon_public = MagicMock()
    svc._catalog = MagicMock()
    svc._media_repo = MagicMock()
    svc._media_repo.resolve_attached_media_id.return_value = None
    svc._salon_public.resolve_public_salon_by_slug.return_value = _entry()
    first = _service(name="A", sort_order=0)
    first.id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    second = _service(name="B", sort_order=1)
    second.id = uuid.UUID("22222222-2222-4222-8222-222222222222")
    svc._catalog.list_services.return_value = [first, second]

    result = svc.list_active_services_by_slug("demo")

    assert [s.name for s in result.services] == ["A", "B"]


@patch.object(PublicCatalogService, "__init__", lambda self, session: None)
def test_list_bookable_staff_only_assigned_active_bookable() -> None:
    svc = PublicCatalogService(MagicMock())
    svc._salon_public = MagicMock()
    svc._availability_repo = MagicMock()
    svc._staff_repo = MagicMock()
    svc._media_repo = MagicMock()
    svc._media_repo.resolve_attached_media_id.return_value = None
    svc._salon_public.resolve_public_salon_by_slug.return_value = _entry()
    svc._availability_repo.get_active_service_for_availability.return_value = MagicMock()
    svc._availability_repo.list_bookable_staff_for_service.return_value = [
        STAFF_ASSIGNED
    ]
    staff_row = MagicMock()
    staff_row.id = STAFF_ASSIGNED
    staff_row.display_name = "Alex"
    svc._staff_repo.get_staff_by_id.return_value = staff_row

    result = svc.list_bookable_staff_for_service_by_slug(
        slug="demo", service_id=SERVICE_ID
    )

    assert len(result.staff) == 1
    assert result.staff[0].display_name == "Alex"
    svc._availability_repo.list_bookable_staff_for_service.assert_called_once_with(
        SALON_A, SERVICE_ID
    )


@patch.object(PublicCatalogService, "__init__", lambda self, session: None)
def test_list_bookable_staff_excludes_unassigned_via_repo() -> None:
    svc = PublicCatalogService(MagicMock())
    svc._salon_public = MagicMock()
    svc._availability_repo = MagicMock()
    svc._staff_repo = MagicMock()
    svc._salon_public.resolve_public_salon_by_slug.return_value = _entry()
    svc._availability_repo.get_active_service_for_availability.return_value = MagicMock()
    svc._availability_repo.list_bookable_staff_for_service.return_value = []

    result = svc.list_bookable_staff_for_service_by_slug(
        slug="demo", service_id=SERVICE_ID
    )

    assert result.staff == ()
    svc._staff_repo.get_staff_by_id.assert_not_called()


@patch.object(PublicCatalogService, "__init__", lambda self, session: None)
def test_list_bookable_staff_inactive_service_404() -> None:
    svc = PublicCatalogService(MagicMock())
    svc._salon_public = MagicMock()
    svc._availability_repo = MagicMock()
    svc._salon_public.resolve_public_salon_by_slug.return_value = _entry()
    svc._availability_repo.get_active_service_for_availability.return_value = None

    with pytest.raises(ServiceCatalogNotFoundError):
        svc.list_bookable_staff_for_service_by_slug(
            slug="demo", service_id=SERVICE_ID
        )


@patch.object(PublicCatalogService, "__init__", lambda self, session: None)
def test_list_bookable_staff_wrong_tenant_service_404() -> None:
    svc = PublicCatalogService(MagicMock())
    svc._salon_public = MagicMock()
    svc._availability_repo = MagicMock()
    svc._salon_public.resolve_public_salon_by_slug.return_value = _entry()
    svc._availability_repo.get_active_service_for_availability.return_value = None

    with pytest.raises(ServiceCatalogNotFoundError):
        svc.list_bookable_staff_for_service_by_slug(
            slug="demo",
            service_id=STAFF_UNASSIGNED,
        )

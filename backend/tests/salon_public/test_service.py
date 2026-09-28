from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.db.models.salon import Salon
from app.services.salon_public.errors import PublicSalonNotFoundError
from app.services.salon_public.service import SalonPublicService
from app.services.salon_public.types import PublicSalonEntry

SALON_A = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
SALON_B = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


def _salon(
    *,
    salon_id: uuid.UUID,
    slug: str,
    name: str,
    active: bool = True,
) -> Salon:
    return Salon(
        id=salon_id,
        name=name,
        slug=slug,
        timezone="Asia/Almaty",
        currency_code="KZT",
        is_active=active,
    )


def test_resolve_returns_public_fields_only() -> None:
    svc = SalonPublicService(MagicMock())
    salon = _salon(salon_id=SALON_A, slug="liman-a", name="Liman A")
    svc._repo.get_active_salon_by_slug = MagicMock(return_value=salon)
    svc._media_repo.resolve_attached_media_id = MagicMock(return_value=None)

    entry = svc.resolve_public_salon_by_slug("liman-a")

    assert entry == PublicSalonEntry(
        salon_id=SALON_A,
        slug="liman-a",
        name="Liman A",
        currency_code="KZT",
        timezone="Asia/Almaty",
        logo_media_id=None,
    )
    svc._repo.get_active_salon_by_slug.assert_called_once_with("liman-a")


def test_resolve_normalizes_slug_for_lookup() -> None:
    svc = SalonPublicService(MagicMock())
    svc._repo.get_active_salon_by_slug = MagicMock(return_value=None)

    with pytest.raises(PublicSalonNotFoundError):
        svc.resolve_public_salon_by_slug("  Liman Demo ")

    svc._repo.get_active_salon_by_slug.assert_called_once_with("liman-demo")


def test_resolve_not_found_inactive_or_missing() -> None:
    svc = SalonPublicService(MagicMock())
    svc._repo.get_active_salon_by_slug = MagicMock(return_value=None)

    with pytest.raises(PublicSalonNotFoundError):
        svc.resolve_public_salon_by_slug("missing")


def test_two_salons_resolve_distinct_by_slug() -> None:
    svc = SalonPublicService(MagicMock())
    salon_a = _salon(salon_id=SALON_A, slug="salon-a", name="A")
    salon_b = _salon(salon_id=SALON_B, slug="salon-b", name="B")

    def _lookup(slug: str) -> Salon | None:
        if slug == "salon-a":
            return salon_a
        if slug == "salon-b":
            return salon_b
        return None

    svc._repo.get_active_salon_by_slug = MagicMock(side_effect=_lookup)
    svc._media_repo.resolve_attached_media_id = MagicMock(return_value=None)

    a = svc.resolve_public_salon_by_slug("salon-a")
    b = svc.resolve_public_salon_by_slug("salon-b")

    assert a.salon_id == SALON_A
    assert b.salon_id == SALON_B

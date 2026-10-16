from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.media.types import MediaEntityType, MediaPurpose
from app.services.salon_public.service import SalonPublicService
from app.services.salon_public.types import PublicSalonAppearanceColors


SALON_ID = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


def test_public_entry_includes_safe_appearance_and_cover() -> None:
    session = MagicMock()
    svc = SalonPublicService(session)
    svc._repo = MagicMock()
    svc._media_repo = MagicMock()

    svc._repo.get_active_salon_by_slug.return_value = SimpleNamespace(
        id=SALON_ID,
        slug="demo",
        name="Demo Salon",
        currency_code="KGS",
        timezone="Asia/Bishkek",
        appearance={
            "v": 1,
            "primary_color": "#1e4d7b",
            "accent_soft_color": "#e3eef8",
            "background_color": "#f5f7fa",
        },
    )

    def resolve(**kwargs):  # noqa: ANN003
        purpose = kwargs["purpose"]
        if purpose is MediaPurpose.LOGO:
            return uuid.UUID("11111111-1111-4111-8111-111111111111")
        if purpose is MediaPurpose.COVER:
            return uuid.UUID("22222222-2222-4222-8222-222222222222")
        return None

    svc._media_repo.resolve_attached_media_id.side_effect = resolve

    entry = svc.resolve_public_salon_by_slug("demo")
    assert entry.name == "Demo Salon"
    assert entry.logo_media_id is not None
    assert entry.background_media_id is not None
    assert entry.appearance == PublicSalonAppearanceColors(
        primary_color="#1e4d7b",
        accent_soft_color="#e3eef8",
        background_color="#f5f7fa",
    )
    # Business settings must not appear on the public entry type
    assert not hasattr(entry, "settings")
    assert svc._media_repo.resolve_attached_media_id.call_count == 2
    calls = svc._media_repo.resolve_attached_media_id.call_args_list
    assert calls[0].kwargs["entity_type"] is MediaEntityType.SALON
    assert calls[0].kwargs["purpose"] is MediaPurpose.LOGO
    assert calls[1].kwargs["purpose"] is MediaPurpose.COVER


def test_public_entry_omits_appearance_when_empty() -> None:
    session = MagicMock()
    svc = SalonPublicService(session)
    svc._repo = MagicMock()
    svc._media_repo = MagicMock()
    svc._repo.get_active_salon_by_slug.return_value = SimpleNamespace(
        id=SALON_ID,
        slug="demo",
        name="Demo",
        currency_code="KGS",
        timezone="UTC",
        appearance={},
    )
    svc._media_repo.resolve_attached_media_id.return_value = None
    entry = svc.resolve_public_salon_by_slug("demo")
    assert entry.appearance is None
    assert entry.background_media_id is None

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.services.salon_appearance.schema import SalonAppearanceColorsPatch
from app.services.salon_appearance.service import (
    SalonAppearancePatchData,
    SalonAppearanceService,
    merge_appearance_patch,
    validate_stored_appearance,
)

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


def test_validate_empty_and_colors() -> None:
    assert validate_stored_appearance({}) == {}
    assert validate_stored_appearance(
        {
            "v": 1,
            "primary_color": "#2F6B4F",
            "accent_soft_color": "#E8F2EC",
            "background_color": "#F4F7F5",
        }
    ) == {
        "v": 1,
        "primary_color": "#2f6b4f",
        "accent_soft_color": "#e8f2ec",
        "background_color": "#f4f7f5",
    }


def test_validate_rejects_unsafe_color() -> None:
    with pytest.raises(Exception):
        validate_stored_appearance({"v": 1, "primary_color": "javascript:alert(1)"})


def test_merge_patch_set_and_clear() -> None:
    current = {"v": 1, "primary_color": "#111111"}
    merged = merge_appearance_patch(
        current,
        SalonAppearancePatchData(
            colors_set=True,
            colors=SalonAppearanceColorsPatch(
                primary_color="#222222",
                accent_soft_color="#eeeeee",
            ),
        ),
    )
    assert merged["primary_color"] == "#222222"
    assert merged["accent_soft_color"] == "#eeeeee"

    cleared = merge_appearance_patch(
        merged,
        SalonAppearancePatchData(colors_set=True, colors=None),
    )
    assert cleared == {}


def test_service_isolates_salon_reads() -> None:
    session = MagicMock()
    svc = SalonAppearanceService(session)
    svc._repo = MagicMock()
    svc._media_repo = MagicMock()
    svc._repo.salon_exists.side_effect = lambda sid: sid == SALON_A
    svc._repo.get_appearance.return_value = {
        "v": 1,
        "primary_color": "#2f6b4f",
    }
    svc._repo.get_salon_name.return_value = "A"
    svc._media_repo.resolve_attached_media_id.return_value = None

    view_a = svc.get_appearance(salon_id=SALON_A)
    assert view_a.primary_color == "#2f6b4f"
    svc._repo.get_appearance.assert_called_with(SALON_A)

    from app.services.salon_appearance.errors import SalonAppearanceNotFoundError

    with pytest.raises(SalonAppearanceNotFoundError):
        svc.get_appearance(salon_id=SALON_B)

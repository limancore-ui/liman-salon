from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.salon_profile.errors import SalonProfileError, SalonProfileNotFoundError
from app.services.salon_profile.service import (
    SalonProfileService,
    normalize_salon_name,
)

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


def test_normalize_trim_and_reject() -> None:
    assert normalize_salon_name("  Hello  ") == "Hello"
    with pytest.raises(SalonProfileError, match="empty"):
        normalize_salon_name("   ")
    with pytest.raises(SalonProfileError, match="200"):
        normalize_salon_name("x" * 201)


def test_update_name_isolates_salon() -> None:
    session = MagicMock()
    svc = SalonProfileService(session)
    svc._repo = MagicMock()
    svc._repo.get_salon.side_effect = lambda sid: (
        SimpleNamespace(id=SALON_A, name="Old", slug="old")
        if sid == SALON_A
        else None
    )
    svc._repo.update_name.return_value = True

    view = svc.update_name(salon_id=SALON_A, name="  New Name  ")
    assert view.name == "New Name"
    assert view.slug == "old"
    svc._repo.update_name.assert_called_once_with(SALON_A, "New Name")

    with pytest.raises(SalonProfileNotFoundError):
        svc.update_name(salon_id=SALON_B, name="Nope")

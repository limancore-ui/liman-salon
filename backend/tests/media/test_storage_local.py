from __future__ import annotations

import pytest

from app.services.media.errors import MediaValidationError
from app.services.media.storage.local import LocalStorageProvider


def test_local_put_open_delete_round_trip(tmp_path) -> None:
    storage = LocalStorageProvider(tmp_path)
    key = "11111111-1111-4111-8111-111111111111/22222222-2222-4222-8222-222222222222/original.png"
    payload = b"\x89PNG\r\n\x1a\n" + b"data"
    storage.put(key=key, data=payload, content_type="image/png")
    assert storage.exists(key=key)
    assert storage.open(key=key).read() == payload
    storage.delete(key=key)
    assert not storage.exists(key=key)


def test_local_delete_is_idempotent(tmp_path) -> None:
    storage = LocalStorageProvider(tmp_path)
    key = "11111111-1111-4111-8111-111111111111/22222222-2222-4222-8222-222222222222/original.png"
    storage.delete(key=key)


def test_local_rejects_path_traversal(tmp_path) -> None:
    storage = LocalStorageProvider(tmp_path)
    with pytest.raises(MediaValidationError):
        storage.put(key="../escape.png", data=b"x", content_type="image/png")

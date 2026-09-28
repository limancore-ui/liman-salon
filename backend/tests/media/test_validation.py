from __future__ import annotations

import pytest

from app.services.media.errors import MediaValidationError
from app.services.media.validation import (
    magic_bytes_match,
    validate_upload_payload,
)

_MIN_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
_MIN_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
_MIN_WEBP = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 4
_MIN_GIF = b"GIF89a" + b"\x00" * 10


def test_validate_rejects_disallowed_mime() -> None:
    with pytest.raises(MediaValidationError, match="not allowed"):
        validate_upload_payload(
            data=_MIN_PNG,
            content_type="image/svg+xml",
            max_upload_bytes=1024,
        )


def test_validate_rejects_oversized_payload() -> None:
    with pytest.raises(MediaValidationError, match="maximum size"):
        validate_upload_payload(
            data=_MIN_JPEG,
            content_type="image/jpeg",
            max_upload_bytes=4,
        )


def test_validate_rejects_magic_byte_mismatch() -> None:
    with pytest.raises(MediaValidationError, match="does not match"):
        validate_upload_payload(
            data=_MIN_PNG,
            content_type="image/jpeg",
            max_upload_bytes=1024,
        )


def test_validate_accepts_matching_jpeg() -> None:
    normalized = validate_upload_payload(
        data=_MIN_JPEG,
        content_type="image/jpeg; charset=binary",
        max_upload_bytes=1024,
    )
    assert normalized == "image/jpeg"


@pytest.mark.parametrize(
    ("data", "content_type", "expected"),
    [
        (_MIN_JPEG, "image/jpeg", True),
        (_MIN_PNG, "image/png", True),
        (_MIN_WEBP, "image/webp", True),
        (_MIN_GIF, "image/gif", True),
        (_MIN_PNG, "image/jpeg", False),
    ],
)
def test_magic_bytes_match(data: bytes, content_type: str, expected: bool) -> None:
    assert magic_bytes_match(data, content_type) is expected

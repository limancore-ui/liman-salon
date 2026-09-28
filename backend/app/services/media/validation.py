from __future__ import annotations

from app.services.media.errors import MediaValidationError
from app.services.media.types import CONTENT_TYPE_TO_EXTENSION, DEFAULT_ALLOWED_CONTENT_TYPES

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_GIF_MAGIC = b"GIF87a", b"GIF89a"
_WEBP_RIFF = b"RIFF"
_WEBP_MARKER = b"WEBP"


def normalize_content_type(content_type: str) -> str:
    return content_type.split(";", 1)[0].strip().lower()


def extension_for_content_type(content_type: str) -> str:
    normalized = normalize_content_type(content_type)
    ext = CONTENT_TYPE_TO_EXTENSION.get(normalized)
    if ext is None:
        raise MediaValidationError("unsupported content type")
    return ext


def validate_upload_payload(
    *,
    data: bytes,
    content_type: str,
    max_upload_bytes: int,
    allowed_content_types: frozenset[str] | None = None,
) -> str:
    allowlist = allowed_content_types or DEFAULT_ALLOWED_CONTENT_TYPES
    normalized = normalize_content_type(content_type)
    if normalized not in allowlist:
        raise MediaValidationError("content type is not allowed")
    if len(data) == 0:
        raise MediaValidationError("upload is empty")
    if len(data) > max_upload_bytes:
        raise MediaValidationError("upload exceeds maximum size")
    if not magic_bytes_match(data, normalized):
        raise MediaValidationError("file content does not match declared content type")
    return normalized


def magic_bytes_match(data: bytes, content_type: str) -> bool:
    normalized = normalize_content_type(content_type)
    if normalized == "image/jpeg":
        return data.startswith(_JPEG_MAGIC)
    if normalized == "image/png":
        return data.startswith(_PNG_MAGIC)
    if normalized == "image/gif":
        return data.startswith(_GIF_MAGIC)
    if normalized == "image/webp":
        return (
            len(data) >= 12
            and data[:4] == _WEBP_RIFF
            and data[8:12] == _WEBP_MARKER
        )
    return False


def sanitize_original_filename(filename: str) -> str:
    name = filename.strip().replace("\\", "/").split("/")[-1]
    if not name or name in (".", ".."):
        return "upload"
    if len(name) > 255:
        return name[:255]
    return name

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from app.services.media.errors import MediaStorageError, MediaValidationError


class LocalStorageProvider:
    """Filesystem-backed storage rooted at a configured directory."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    def put(self, *, key: str, data: bytes, content_type: str) -> None:
        _ = content_type
        path = self._resolve_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_bytes(data)
        except OSError as exc:
            raise MediaStorageError("failed to write media object") from exc

    def open(self, *, key: str) -> BytesIO:
        path = self._resolve_key(key)
        try:
            return BytesIO(path.read_bytes())
        except OSError as exc:
            raise MediaStorageError("failed to read media object") from exc

    def delete(self, *, key: str) -> None:
        path = self._resolve_key(key)
        try:
            if path.is_file():
                path.unlink()
        except OSError as exc:
            raise MediaStorageError("failed to delete media object") from exc

    def exists(self, *, key: str) -> bool:
        path = self._resolve_key(key)
        return path.is_file()

    def _resolve_key(self, key: str) -> Path:
        if not key or key.startswith("/") or ".." in key.split("/"):
            raise MediaValidationError("invalid storage key")
        relative = Path(*[part for part in key.split("/") if part])
        resolved = (self._root / relative).resolve()
        if self._root not in resolved.parents and resolved != self._root:
            raise MediaValidationError("invalid storage key")
        return resolved

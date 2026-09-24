"""Storage abstraction — wrap MinIO/S3/local filesystem.

Module này thuộc ``shared/storage/`` vì CẢ Backend bounded contexts (contract, extraction)
đều cần upload/read file (PDF gốc, render PNG, thumbnail).

Sprint 3: chỉ impl LocalFileStorage (ghi vào ``./var/storage/``).
Khi scale, thêm ``S3FileStorage`` (MinIO presigned URL) mà không đổi interface.

Frontend gọi /documents/{id}/content để tải file → backend stream từ storage.
Upload qua POST /dossiers/{id}/documents (multipart) → backend lưu qua storage.
"""

from __future__ import annotations

import asyncio
import hashlib
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import BinaryIO

import aiofiles
import structlog

logger = structlog.get_logger(__name__)


class FileStorage(ABC):
    """Abstract storage interface — bounded contexts depend vào interface này."""

    @abstractmethod
    async def put(self, key: str, stream: BinaryIO) -> str:
        """Upload file. Return blob URI (cho lưu DB)."""

    @abstractmethod
    async def get(self, blob_uri: str) -> bytes:
        """Download toàn bộ file thành bytes (dùng cho content endpoint)."""

    @abstractmethod
    def stream(self, blob_uri: str) -> AsyncGenerator[bytes, None]:
        """Stream file theo chunk (tiết kiệm memory cho PDF lớn)."""

    @abstractmethod
    async def exists(self, blob_uri: str) -> bool:
        """Check blob tồn tại."""

    @abstractmethod
    async def delete(self, blob_uri: str) -> None:
        """Xóa file."""


class LocalFileStorage(FileStorage):
    """Filesystem-based storage — dùng cho dev/test khi chưa có MinIO.

    URI format: ``file:///absolute/path`` hoặc ``local://relative/key``.

    Layout:
        ./var/storage/contracts/{document_id}/source.pdf
        ./var/storage/renders/{page_id}.png
        ./var/storage/previews/{page_id}.png
    """

    def __init__(self, root: Path | str = "./var/storage") -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        logger.info("storage.local.init", root=str(self._root))

    def _resolve(self, blob_uri: str) -> Path:
        """Resolve blob URI thành absolute path under storage root.

        Rejects keys that escape ``self._root`` (path traversal).
        """
        if blob_uri.startswith("local://"):
            candidate = self._root / blob_uri[len("local://") :]
        elif blob_uri.startswith("file://"):
            candidate = Path(blob_uri[len("file://") :])
        else:
            candidate = self._root / blob_uri

        resolved = candidate.resolve()
        try:
            resolved.relative_to(self._root)
        except ValueError as exc:
            msg = f"Storage key escapes root: {blob_uri!r}"
            raise ValueError(msg) from exc
        return resolved

    @staticmethod
    def _to_uri(path: Path) -> str:
        """Convert absolute path thành URI để lưu DB."""
        return f"file://{path.as_posix()}"

    async def put(self, key: str, stream: BinaryIO) -> str:
        # Compute SHA-256 trong khi write
        sha = hashlib.sha256()
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)

        loop = asyncio.get_event_loop()

        def _read_sync() -> bytes:
            # Đọc sync từ stream — caller chịu trách nhiệm async upload
            return stream.read()

        data = await loop.run_in_executor(None, _read_sync)
        sha.update(data)

        async with aiofiles.open(target, mode="wb") as f:
            await f.write(data)

        return self._to_uri(target)

    async def get(self, blob_uri: str) -> bytes:
        path = self._resolve(blob_uri)
        if not path.exists():
            msg = f"Blob not found: {blob_uri}"
            raise FileNotFoundError(msg)
        async with aiofiles.open(path, mode="rb") as f:
            return bytes(await f.read())

    async def stream(self, blob_uri: str) -> AsyncGenerator[bytes, None]:
        path = self._resolve(blob_uri)
        if not path.exists():
            msg = f"Blob not found: {blob_uri}"
            raise FileNotFoundError(msg)
        # 64KB chunks — tốt cho PDF ~5MB
        async with aiofiles.open(path, mode="rb") as f:
            while True:
                chunk = await f.read(64 * 1024)
                if not chunk:
                    break
                yield chunk

    async def exists(self, blob_uri: str) -> bool:
        return self._resolve(blob_uri).exists()

    async def delete(self, blob_uri: str) -> None:
        path = self._resolve(blob_uri)
        if path.exists():
            path.unlink()

    async def compute_sha256(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()


# -----------------------------------------------------------------------------
# Singleton
# -----------------------------------------------------------------------------

_storage: FileStorage | None = None


def get_file_storage() -> FileStorage:
    """Singleton — LocalFileStorage mặc định. Swap sang S3 khi có MinIO."""
    global _storage  # noqa: PLW0603
    if _storage is None:
        _storage = LocalFileStorage()
    return _storage


def set_file_storage(storage: FileStorage) -> None:
    """Override singleton — dùng trong test fixture."""
    global _storage  # noqa: PLW0603
    _storage = storage


def reset_file_storage() -> None:
    global _storage  # noqa: PLW0603
    _storage = None


__all__ = [
    "FileStorage",
    "LocalFileStorage",
    "get_file_storage",
    "reset_file_storage",
    "set_file_storage",
]

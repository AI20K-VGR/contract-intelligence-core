"""MinIO adapter — triển khai BlobStoragePort dùng ``minio`` SDK.

Đây là ranh giới "ngoài" — import MinIO SDK được phép vì infrastructure
được phép phụ thuộc external SDK.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from minio import Minio


@runtime_checkable
class BlobStoragePort(Protocol):
    """Protocol mà application layer tham chiếu tới (qua DI)."""

    async def put_object(self, *, bucket: str, key: str, data: bytes) -> str:
        """Upload + trả về URI để lưu DB."""
        ...

    async def get_object(self, *, bucket: str, key: str) -> bytes: ...
    async def delete_object(self, *, bucket: str, key: str) -> None: ...


class MinioBlobStorage:
    """Concrete adapter cho MinIO."""

    def __init__(self, client: Minio) -> None:
        self._client = client

    async def put_object(self, *, bucket: str, key: str, data: bytes) -> str:
        # Sprint 2: import asyncio.to_thread để gọi blocking put_object
        raise NotImplementedError("Sprint 2 — implement async wrapper cho MinIO client")

    async def get_object(self, *, bucket: str, key: str) -> bytes:
        raise NotImplementedError

    async def delete_object(self, *, bucket: str, key: str) -> None:
        raise NotImplementedError


_: type[BlobStoragePort] = MinioBlobStorage

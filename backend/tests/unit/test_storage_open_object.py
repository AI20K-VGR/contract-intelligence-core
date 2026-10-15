"""``open_object``: MinIO reads stream chunk by chunk and honour one byte range."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from botocore.exceptions import ClientError

from contract_intelligence.infrastructure import storage as storage_module

# Bound at import, before the autouse fixture in conftest swaps in a fake.
from contract_intelligence.infrastructure.storage import open_object
from contract_intelligence.shared.storage import ByteRange, RangeNotSatisfiableError

_DATA = b"0123456789" * 100


class _Body:
    def __init__(self, data: bytes) -> None:
        self._data = data

    async def iter_chunks(self, chunk_size: int) -> AsyncIterator[bytes]:
        for offset in range(0, len(self._data), chunk_size):
            yield self._data[offset : offset + chunk_size]


class _FakeS3:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.requests: list[dict[str, Any]] = []
        self.closed = False

    async def __aenter__(self) -> _FakeS3:
        return self

    async def __aexit__(self, *_: object) -> None:
        self.closed = True

    async def get_object(self, **request: Any) -> dict[str, Any]:
        self.requests.append(request)
        if request["Key"] == "missing.pdf":
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        spec = request.get("Range")
        if spec is None:
            return {"ContentLength": len(self.data), "Body": _Body(self.data)}
        span = ByteRange(*(int(v) if v else None for v in spec.removeprefix("bytes=").split("-")))
        resolved = span.resolve(len(self.data))
        if resolved is None:
            raise ClientError({"Error": {"Code": "InvalidRange"}}, "GetObject")
        first, last = resolved
        piece = self.data[first : last + 1]
        return {
            "ContentLength": len(piece),
            "ContentRange": f"bytes {first}-{last}/{len(self.data)}",
            "Body": _Body(piece),
        }

    async def head_object(self, **_: Any) -> dict[str, Any]:
        return {"ContentLength": len(self.data)}


@pytest.fixture
def s3(monkeypatch: pytest.MonkeyPatch) -> _FakeS3:
    fake = _FakeS3(_DATA)

    class _Session:
        def client(self, **_: Any) -> _FakeS3:
            return fake

    monkeypatch.setattr(storage_module.aioboto3, "Session", _Session)
    return fake


async def _read(stream: Any) -> bytes:
    return b"".join([chunk async for chunk in stream.chunks])


async def test_whole_object_streams_and_closes_the_client(s3: _FakeS3) -> None:
    stream = await open_object("s3://dossiers/contract.pdf")

    assert (stream.size, stream.first, stream.last) == (len(_DATA), 0, len(_DATA) - 1)
    assert not s3.closed
    assert await _read(stream) == _DATA
    assert s3.closed
    assert s3.requests == [{"Bucket": "dossiers", "Key": "contract.pdf"}]


async def test_range_is_forwarded_and_read_from_content_range(s3: _FakeS3) -> None:
    stream = await open_object("s3://dossiers/contract.pdf", byte_range=ByteRange(10, 19))

    assert s3.requests[0]["Range"] == "bytes=10-19"
    assert (stream.size, stream.first, stream.last) == (len(_DATA), 10, 19)
    assert await _read(stream) == _DATA[10:20]


async def test_close_without_reading_releases_the_client(s3: _FakeS3) -> None:
    stream = await open_object("s3://dossiers/contract.pdf")

    await stream.close()

    assert s3.closed


async def test_missing_object_is_file_not_found(s3: _FakeS3) -> None:
    with pytest.raises(FileNotFoundError):
        await open_object("s3://dossiers/missing.pdf")
    assert s3.closed


async def test_range_past_the_end_reports_the_size(s3: _FakeS3) -> None:
    with pytest.raises(RangeNotSatisfiableError) as caught:
        await open_object("s3://dossiers/contract.pdf", byte_range=ByteRange(5000, None))
    assert caught.value.size == len(_DATA)
    assert s3.closed

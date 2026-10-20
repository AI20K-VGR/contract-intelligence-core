"""The chunked upload tests again, on a real MinIO instead of the in-memory stub.

The stub in tests/conftest.py stores bytes in a dict; this module puts the real
``infrastructure.storage`` functions back and points them at the MinIO given in
``CI_TEST_MINIO_URL``, so chunk keys, overwrites, deletes and the join go
through S3 calls. Skipped unless that variable is set, e.g.::

    docker run -d --name ci-minio-test --user 0:0 -p 127.0.0.1:59000:9000 \\
      -e MINIO_ROOT_USER=citest -e MINIO_ROOT_PASSWORD=citest-secret-123 \\
      cgr.dev/chainguard/minio:latest server /data
    CI_TEST_MINIO_URL=http://127.0.0.1:59000 CI_TEST_MINIO_USER=citest \\
      CI_TEST_MINIO_PASSWORD=citest-secret-123 \\
      uv run pytest tests/integration/test_upload_sessions_minio.py
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock

import aioboto3
import pytest
from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contract_intelligence.contract.infrastructure.persistence.upload_session_store import (
    UploadChunkORM,
    UploadSessionORM,
)
from contract_intelligence.infrastructure import storage

# Captured at import, before the autouse stub replaces them for each test.
_REAL_UPLOAD = storage.upload_file
_REAL_DOWNLOAD = storage.download_object
_REAL_OPEN = storage.open_object
_REAL_DELETE = storage.delete_object

from tests.integration.test_upload_sessions import (  # noqa: E402
    TestChunks,
    TestConcurrency,
    TestHappyPath,
    TestJoinOrder,
    TestOrphanFiles,
    TestOwnershipAndLifecycle,
    _settings,
    client,
    db,
    headers,
)

MINIO_URL = os.environ.get("CI_TEST_MINIO_URL", "")
BUCKET = "dossiers"  # the tests address objects as s3://dossiers/...

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not MINIO_URL, reason="CI_TEST_MINIO_URL not set"),
]

__all__ = [
    "TestChunks",
    "TestConcurrency",
    "TestHappyPath",
    "TestJoinOrder",
    "TestOrphanFiles",
    "TestOwnershipAndLifecycle",
    "_settings",
    "client",
    "db",
    "headers",
]


async def _download(object_path: str) -> bytes:
    """Real download; a missing object raises FileNotFoundError like the stub.

    The shared tests assert "deleted" with ``pytest.raises(FileNotFoundError)``;
    MinIO answers NoSuchKey.
    """
    try:
        return await _REAL_DOWNLOAD(object_path)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            raise FileNotFoundError(object_path) from exc
        raise


async def _upload_objects(s3: Any, upload_id: str) -> set[str]:
    prefix = f"uploads/tenant_vgr_01/{upload_id}/"
    found: set[str] = set()
    async for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=prefix):
        found |= {f"s3://{BUCKET}/{item['Key']}" for item in page.get("Contents", [])}
    return found


@pytest.fixture(autouse=True)
async def real_minio(
    mock_minio_and_kafka: None,
    _settings: Any,
    db: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[None]:
    monkeypatch.setattr(_settings, "s3_endpoint_url", MINIO_URL)
    monkeypatch.setattr(_settings, "s3_access_key", os.environ.get("CI_TEST_MINIO_USER", ""))
    monkeypatch.setattr(_settings, "s3_secret_key", os.environ.get("CI_TEST_MINIO_PASSWORD", ""))
    monkeypatch.setattr(_settings, "s3_bucket_name", BUCKET)
    session = aioboto3.Session()
    async with session.client(**storage._s3_client_kwargs()) as s3:
        try:
            await s3.create_bucket(Bucket=BUCKET)
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in (
                "BucketAlreadyOwnedByYou",
                "BucketAlreadyExists",
            ):
                raise
    # AsyncMock keeps await_args_list, which one shared test reads.
    monkeypatch.setattr(storage, "upload_file", AsyncMock(side_effect=_REAL_UPLOAD))
    monkeypatch.setattr(storage, "download_object", _download)
    monkeypatch.setattr(storage, "open_object", _REAL_OPEN)
    monkeypatch.setattr(storage, "delete_object", _REAL_DELETE)
    yield

    # No leak and nothing missing: the chunk objects MinIO holds for this test's
    # sessions are exactly the ones their chunk rows point to.
    async with db() as s:
        upload_ids = list((await s.execute(select(UploadSessionORM.id))).scalars())
        referenced = set((await s.execute(select(UploadChunkORM.object_path))).scalars())
    async with session.client(**storage._s3_client_kwargs()) as s3:
        stored: set[str] = set()
        for upload_id in upload_ids:
            stored |= await _upload_objects(s3, upload_id)
    assert stored == referenced, {
        "left_behind": stored - referenced,
        "missing": referenced - stored,
    }

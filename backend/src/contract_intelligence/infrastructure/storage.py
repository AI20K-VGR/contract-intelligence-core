"""Async MinIO / S3 file upload and download via aioboto3."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Any
from urllib.parse import urlparse

import aioboto3
import structlog
from botocore.config import Config
from botocore.exceptions import ClientError

from contract_intelligence.config.settings import get_settings
from contract_intelligence.shared.storage import (
    STREAM_CHUNK_BYTES,
    ByteRange,
    ObjectStream,
    RangeNotSatisfiableError,
)

logger = structlog.get_logger(__name__)


def parse_s3_uri(object_path: str) -> tuple[str, str]:
    """Parse ``s3://bucket/key`` or bare key into ``(bucket, key)``."""
    settings = get_settings()
    if object_path.startswith("s3://"):
        without = object_path[len("s3://") :]
        bucket, _, key = without.partition("/")
        if not bucket or not key:
            msg = f"Invalid s3 URI: {object_path!r}"
            raise ValueError(msg)
        return bucket, key
    return settings.s3_bucket_name, object_path.lstrip("/")


def ai1_result_key(document_id: str, run_id: str) -> str:
    """Render-bucket key AI1 may upload an OCR result to (one per run + document)."""
    return f"{document_id}/ai1-result/{run_id}.json"


def ai1_result_uri(document_id: str, run_id: str) -> str:
    return f"s3://{get_settings().minio_bucket_render}/{ai1_result_key(document_id, run_id)}"


def _s3_client_kwargs() -> dict[str, Any]:
    settings = get_settings()
    return {
        "service_name": "s3",
        "endpoint_url": settings.s3_endpoint_url,
        "aws_access_key_id": settings.s3_access_key,
        "aws_secret_access_key": settings.s3_secret_key,
        "region_name": "us-east-1",
        "config": Config(signature_version="s3v4"),
    }


async def upload_file(file_name: str, file_data: bytes) -> str:
    """Upload ``file_data`` to the configured S3 bucket.

    Returns:
        Object path in the form ``s3://{bucket}/{key}``.
    """
    settings = get_settings()
    bucket = settings.s3_bucket_name
    key = file_name.lstrip("/")

    session = aioboto3.Session()
    async with session.client(**_s3_client_kwargs()) as s3:
        await s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=file_data,
            ContentType=_guess_content_type(key),
        )

    object_path = f"s3://{bucket}/{key}"
    logger.info(
        "storage.upload_ok",
        bucket=bucket,
        key=key,
        size_bytes=len(file_data),
        object_path=object_path,
    )
    return object_path


async def download_object(object_path: str) -> bytes:
    """Download object bytes from S3/MinIO (``s3://bucket/key`` or bare key)."""
    bucket, key = parse_s3_uri(object_path)
    session = aioboto3.Session()
    async with session.client(**_s3_client_kwargs()) as s3:
        response = await s3.get_object(Bucket=bucket, Key=key.lstrip("/"))
        body = response["Body"]
        data: bytes = await body.read()
    logger.info("storage.download_ok", bucket=bucket, key=key, size_bytes=len(data))
    return data


async def open_object(object_path: str, *, byte_range: ByteRange | None = None) -> ObjectStream:
    """Open an S3/MinIO object (or one range of it) for reading chunk by chunk.

    Nothing is buffered: the first chunk goes out as soon as MinIO sends it.
    Raises ``FileNotFoundError`` for a missing object and
    :class:`RangeNotSatisfiableError` for a range outside it.
    """
    bucket, key = parse_s3_uri(object_path)
    key = key.lstrip("/")
    stack = AsyncExitStack()
    try:
        s3 = await stack.enter_async_context(aioboto3.Session().client(**_s3_client_kwargs()))
        request: dict[str, Any] = {"Bucket": bucket, "Key": key}
        if byte_range is not None:
            request["Range"] = byte_range.header()
        try:
            response = await s3.get_object(**request)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in ("NoSuchKey", "404"):
                raise FileNotFoundError(object_path) from exc
            if code == "InvalidRange":
                head = await s3.head_object(Bucket=bucket, Key=key)
                raise RangeNotSatisfiableError(int(head["ContentLength"])) from exc
            raise
    except BaseException:
        await stack.aclose()
        raise

    length = int(response["ContentLength"])
    first, last, size = 0, length - 1, length
    content_range = response.get("ContentRange")  # "bytes first-last/size"
    if content_range:
        span, _, total = str(content_range).removeprefix("bytes ").partition("/")
        first_text, _, last_text = span.partition("-")
        first, last, size = int(first_text), int(last_text), int(total)
    body = response["Body"]

    async def chunks() -> AsyncIterator[bytes]:
        try:
            async for chunk in body.iter_chunks(STREAM_CHUNK_BYTES):
                yield chunk
        finally:
            await stack.aclose()

    return ObjectStream(size=size, first=first, last=last, chunks=chunks(), close=stack.aclose)


async def delete_object(object_path: str) -> None:
    """Best-effort delete of an S3/MinIO object (``s3://bucket/key`` or bare key)."""
    bucket, key = parse_s3_uri(object_path)
    session = aioboto3.Session()
    async with session.client(**_s3_client_kwargs()) as s3:
        await s3.delete_object(Bucket=bucket, Key=key.lstrip("/"))
    logger.info("storage.delete_ok", bucket=bucket, key=key)


async def generate_presigned_get_url(
    object_path: str,
    *,
    expires_in: int | None = None,
) -> str:
    """Return a short-lived GET URL for ``object_path`` (``s3://bucket/key``)."""
    settings = get_settings()
    bucket, key = parse_s3_uri(object_path)
    ttl = expires_in if expires_in is not None else settings.kafka_presign_expires_seconds
    session = aioboto3.Session()
    async with session.client(**_s3_client_kwargs()) as s3:
        url: str = await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=ttl,
        )
    return url


async def generate_presigned_put_url(
    *,
    key: str,
    bucket: str | None = None,
    content_type: str = "image/png",
    expires_in: int | None = None,
) -> str:
    """Return a short-lived PUT URL for uploading a render artifact."""
    settings = get_settings()
    target_bucket = bucket or settings.minio_bucket_render
    ttl = expires_in if expires_in is not None else settings.kafka_presign_expires_seconds
    session = aioboto3.Session()
    async with session.client(**_s3_client_kwargs()) as s3:
        # Ensure render bucket exists in local/dev (idempotent).
        try:
            await s3.head_bucket(Bucket=target_bucket)
        except Exception:
            try:
                await s3.create_bucket(Bucket=target_bucket)
            except Exception as exc:
                logger.warning(
                    "storage.render_bucket_create_failed",
                    bucket=target_bucket,
                    error=str(exc),
                )
        url: str = await s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": target_bucket,
                "Key": key.lstrip("/"),
                "ContentType": content_type,
            },
            ExpiresIn=ttl,
        )
    return url


def rewrite_presigned_host(url: str, *, public_endpoint: str | None = None) -> str:
    """Optionally rewrite host for callers on a different network namespace."""
    if not public_endpoint:
        return url
    parsed = urlparse(url)
    target = urlparse(public_endpoint)
    return parsed._replace(
        scheme=target.scheme or parsed.scheme,
        netloc=target.netloc or parsed.netloc,
    ).geturl()


def _guess_content_type(key: str) -> str:
    lower = key.lower()
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith(".png"):
        return "image/png"
    return "application/octet-stream"

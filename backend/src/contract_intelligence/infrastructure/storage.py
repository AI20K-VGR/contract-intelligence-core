"""Async MinIO / S3 file upload via aioboto3."""

from __future__ import annotations

import aioboto3
import structlog
from botocore.config import Config

from contract_intelligence.config.settings import get_settings

logger = structlog.get_logger(__name__)


async def upload_file(file_name: str, file_data: bytes) -> str:
    """Upload ``file_data`` to the configured S3 bucket.

    Returns:
        Object path in the form ``s3://{bucket}/{key}``.
    """
    settings = get_settings()
    bucket = settings.s3_bucket_name
    key = file_name.lstrip("/")

    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    ) as s3:
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


def _guess_content_type(key: str) -> str:
    lower = key.lower()
    if lower.endswith(".pdf"):
        return "application/pdf"
    return "application/octet-stream"

"""S3-compatible storage backend using boto3.

Works with AWS S3, Cloudflare R2, Backblaze B2, MinIO, and
Supabase Storage by setting S3_ENDPOINT_URL to the provider's
S3-compatible endpoint.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Any

from calllens.core.config import get_settings

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 64 * 1024  # 64 KiB


@lru_cache(maxsize=1)
def _get_boto3_client() -> Any:
    """Create and cache a boto3 S3 client from settings.

    Returns:
        A boto3 S3 client.

    Raises:
        ImportError: If boto3 is not installed.
        ValueError: If required S3 settings are missing.
    """
    try:
        import boto3
    except ImportError as exc:
        raise ImportError("boto3 is not installed. Run: uv add boto3") from exc

    settings = get_settings()
    if not settings.s3_bucket:
        raise ValueError("S3_BUCKET is required when STORAGE_BACKEND=s3")
    if not settings.s3_access_key_id or not settings.s3_secret_access_key:
        raise ValueError(
            "S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY are required when STORAGE_BACKEND=s3"
        )

    kwargs: dict[str, str] = {
        "region_name": settings.s3_region,
        "aws_access_key_id": settings.s3_access_key_id,
        "aws_secret_access_key": settings.s3_secret_access_key,
    }
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url

    return boto3.client("s3", **kwargs)


class S3Storage:
    """S3-compatible object storage backend.

    All operations are run in a thread pool executor since boto3 is synchronous.

    Args:
        bucket: S3 bucket name.
        client: Optional pre-configured boto3 S3 client (for testing).
    """

    def __init__(self, bucket: str, client: Any | None = None) -> None:
        self._bucket = bucket
        self._client = client

    @property
    def _s3(self) -> Any:
        if self._client is not None:
            return self._client
        return _get_boto3_client()

    async def save(self, data: bytes, key: str) -> str:
        """Upload bytes to S3.

        Args:
            data: Raw file bytes.
            key: Object key within the bucket.

        Returns:
            The key used.
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, lambda: self._s3.put_object(Bucket=self._bucket, Key=key, Body=data)
        )
        logger.debug("Saved to S3", extra={"key": key, "bytes": len(data)})
        return key

    async def open_stream(
        self, key: str, *, start: int = 0, end: int | None = None
    ) -> AsyncGenerator[bytes, None]:
        """Stream object bytes from S3 with optional byte-range.

        Passes the Range header to S3 GetObject for server-side
        byte serving — no full-object download needed for Range requests.

        Args:
            key: Object key.
            start: First byte offset (inclusive).
            end: Last byte offset (exclusive). None = stream to EOF.

        Yields:
            Chunks of up to 64 KiB.
        """
        loop = asyncio.get_event_loop()
        kwargs: dict[str, object] = {"Bucket": self._bucket, "Key": key}
        if start or end is not None:
            range_str = f"bytes={start}-"
            if end is not None:
                range_str = f"bytes={start}-{end - 1}"
            kwargs["Range"] = range_str

        response = await loop.run_in_executor(None, lambda: self._s3.get_object(**kwargs))
        body = response["Body"]

        try:
            while True:
                chunk = await loop.run_in_executor(None, lambda: body.read(_CHUNK_SIZE))
                if not chunk:
                    break
                yield chunk
        finally:
            await loop.run_in_executor(None, body.close)

    async def file_size(self, key: str) -> int:
        """Return the byte size of the stored object via HeadObject.

        Args:
            key: Object key.

        Returns:
            Object size in bytes.
        """
        loop = asyncio.get_event_loop()
        head = await loop.run_in_executor(
            None,
            lambda: self._s3.head_object(Bucket=self._bucket, Key=key),
        )
        return int(head["ContentLength"])

    async def delete(self, key: str) -> None:
        """Delete an object from S3.

        Args:
            key: Object key.
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, lambda: self._s3.delete_object(Bucket=self._bucket, Key=key)
        )
        logger.debug("Deleted from S3", extra={"key": key})

    async def exists(self, key: str) -> bool:
        """Check whether an object exists via HeadObject.

        Args:
            key: Object key.

        Returns:
            True if the object exists.
        """
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._s3.head_object(Bucket=self._bucket, Key=key),
            )
            return True
        except Exception:
            return False

"""S3 storage backend stub — requires the optional boto3 dependency."""

from collections.abc import AsyncGenerator


class S3Storage:
    """AWS S3 storage backend.

    Requires boto3 to be installed. Currently a stub; implement when
    STORAGE_BACKEND=s3 is needed.

    Args:
        bucket: S3 bucket name.
        prefix: Key prefix prepended to every storage key.
    """

    def __init__(self, bucket: str, prefix: str = "") -> None:
        self._bucket = bucket
        self._prefix = prefix

    async def save(self, data: bytes, key: str) -> str:
        """TODO: upload bytes to S3 via boto3."""
        raise NotImplementedError("S3Storage.save is not yet implemented")

    async def open_stream(
        self, key: str, *, start: int = 0, end: int | None = None
    ) -> AsyncGenerator[bytes, None]:
        """TODO: stream object from S3 with Range header support."""
        raise NotImplementedError("S3Storage.open_stream is not yet implemented")
        yield b""  # makes this a generator for the type checker

    async def file_size(self, key: str) -> int:
        """TODO: return object size via HeadObject."""
        raise NotImplementedError("S3Storage.file_size is not yet implemented")

    async def delete(self, key: str) -> None:
        """TODO: delete object from S3."""
        raise NotImplementedError("S3Storage.delete is not yet implemented")

    async def exists(self, key: str) -> bool:
        """TODO: check object existence via HeadObject."""
        raise NotImplementedError("S3Storage.exists is not yet implemented")

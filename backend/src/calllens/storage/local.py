"""Local filesystem storage backend using aiofiles."""

import logging
from collections.abc import AsyncGenerator
from pathlib import Path

import aiofiles
import aiofiles.os

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 64 * 1024  # 64 KiB


class LocalStorage:
    """Stores files on the local filesystem under a configurable root directory.

    Args:
        root: Directory under which all files are stored.
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, key: str) -> Path:
        return self._root / key

    async def save(self, data: bytes, key: str) -> str:
        """Write bytes to disk, creating parent directories as needed.

        Args:
            data: File bytes to write.
            key: Relative path under the storage root.

        Returns:
            The key passed in.
        """
        target = self._path(key)
        await aiofiles.os.makedirs(str(target.parent), exist_ok=True)
        async with aiofiles.open(target, "wb") as f:
            await f.write(data)
        logger.debug("Saved file", extra={"key": key, "bytes": len(data)})
        return key

    async def open_stream(
        self, key: str, *, start: int = 0, end: int | None = None
    ) -> AsyncGenerator[bytes, None]:
        """Yield file bytes within the requested byte range.

        Args:
            key: Storage key of the file.
            start: First byte offset (inclusive).
            end: Last byte offset (exclusive). None streams to EOF.

        Yields:
            Chunks of up to 64 KiB.
        """
        target = self._path(key)
        async with aiofiles.open(target, "rb") as f:
            if start:
                await f.seek(start)
            remaining = (end - start) if end is not None else None
            while True:
                to_read = _CHUNK_SIZE if remaining is None else min(_CHUNK_SIZE, remaining)
                chunk = await f.read(to_read)
                if not chunk:
                    break
                yield chunk
                if remaining is not None:
                    remaining -= len(chunk)
                    if remaining <= 0:
                        break

    async def file_size(self, key: str) -> int:
        """Return the byte size of a stored file.

        Args:
            key: Storage key.

        Returns:
            File size in bytes.
        """
        stat = await aiofiles.os.stat(str(self._path(key)))
        return int(stat.st_size)

    async def delete(self, key: str) -> None:
        """Delete a stored file.

        Args:
            key: Storage key.
        """
        await aiofiles.os.remove(str(self._path(key)))
        logger.debug("Deleted file", extra={"key": key})

    async def exists(self, key: str) -> bool:
        """Check whether a file exists.

        Args:
            key: Storage key.

        Returns:
            True if the file exists.
        """
        return self._path(key).exists()

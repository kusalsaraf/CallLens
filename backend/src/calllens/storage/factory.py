"""Factory for selecting the configured storage backend."""

from calllens.core.config import get_settings
from calllens.storage.base import StorageBackend


def get_storage() -> StorageBackend:
    """Return a StorageBackend instance configured from application settings.

    Returns:
        The appropriate StorageBackend for the configured STORAGE_BACKEND.

    Raises:
        ValueError: If STORAGE_BACKEND is set to an unrecognised value, or
            if required S3 settings are missing.
    """
    settings = get_settings()
    if settings.storage_backend == "local":
        from calllens.storage.local import LocalStorage

        return LocalStorage(root=settings.local_storage_dir)
    if settings.storage_backend == "s3":
        if not settings.s3_bucket:
            raise ValueError("S3_BUCKET is required when STORAGE_BACKEND=s3")
        from calllens.storage.s3 import S3Storage

        return S3Storage(bucket=settings.s3_bucket)
    raise ValueError(f"Unknown storage backend: {settings.storage_backend!r}")

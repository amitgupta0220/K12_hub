"""Object-storage abstractions for raw-file ingestion."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from minio import Minio
from minio.error import MinioException

from k12hub.config import MinioSettings


class ObjectStorageError(RuntimeError):
    """Raised when an object cannot be uploaded."""


class ObjectStorageClient(Protocol):
    """Minimal object-storage behavior required by ingestion and staging."""

    def upload_file(self, bucket: str, object_path: str, local_path: Path) -> None:
        """Upload one local file without changing it."""

    def read_object(self, bucket: str, object_path: str) -> bytes:
        """Read one immutable object for parsing."""


class MinioObjectStorageClient:
    """S3-compatible object storage implemented with MinIO."""

    def __init__(self, settings: MinioSettings) -> None:
        self._client = Minio(
            endpoint=settings.endpoint,
            access_key=settings.access_key,
            secret_key=settings.secret_key,
            secure=settings.secure,
        )

    def upload_file(self, bucket: str, object_path: str, local_path: Path) -> None:
        """Upload a local file to a configured MinIO bucket."""

        try:
            self._client.fput_object(bucket, object_path, str(local_path))
        except (MinioException, OSError) as error:
            raise ObjectStorageError(
                f"Unable to upload {local_path.name} to {bucket}/{object_path}"
            ) from error

    def read_object(self, bucket: str, object_path: str) -> bytes:
        """Read an object from MinIO and release its HTTP connection."""

        response = None
        try:
            response = self._client.get_object(bucket, object_path)
            return response.read()
        except (MinioException, OSError) as error:
            raise ObjectStorageError(f"Unable to read {bucket}/{object_path}") from error
        finally:
            if response is not None:
                response.close()
                response.release_conn()

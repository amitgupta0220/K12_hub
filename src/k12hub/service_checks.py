"""Connectivity checks for local infrastructure services."""

from __future__ import annotations

import psycopg
from minio import Minio
from minio.error import MinioException

from k12hub.config import MinioSettings, PostgresSettings, Settings


class ServiceCheckError(RuntimeError):
    """Raised when a local infrastructure service is unavailable or incomplete."""


def check_postgres(settings: PostgresSettings) -> None:
    """Verify that PostgreSQL accepts a connection and a read-only query."""

    try:
        with psycopg.connect(
            host=settings.host,
            port=settings.port,
            dbname=settings.database,
            user=settings.user,
            password=settings.password,
            connect_timeout=5,
        ) as connection:
            result = connection.execute("SELECT %s", (1,)).fetchone()
    except psycopg.Error as error:
        raise ServiceCheckError("PostgreSQL connectivity check failed") from error

    if result != (1,):
        raise ServiceCheckError("PostgreSQL connectivity check returned an unexpected result")


def check_minio(settings: MinioSettings) -> None:
    """Verify that MinIO is reachable and all required buckets exist."""

    client = Minio(
        endpoint=settings.endpoint,
        access_key=settings.access_key,
        secret_key=settings.secret_key,
        secure=settings.secure,
    )
    try:
        missing_buckets = [
            bucket for bucket in settings.buckets if not client.bucket_exists(bucket)
        ]
    except (MinioException, OSError) as error:
        raise ServiceCheckError("MinIO connectivity check failed") from error

    if missing_buckets:
        missing = ", ".join(missing_buckets)
        raise ServiceCheckError(f"MinIO is missing required buckets: {missing}")


def check_services(settings: Settings) -> None:
    """Run all local infrastructure connectivity checks."""

    check_postgres(settings.postgres)
    check_minio(settings.minio)

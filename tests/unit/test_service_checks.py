from unittest.mock import MagicMock, patch

import pytest
from minio.error import S3Error
from psycopg import OperationalError

from k12hub.config import MinioSettings, PostgresSettings
from k12hub.service_checks import ServiceCheckError, check_minio, check_postgres


@patch("k12hub.service_checks.psycopg.connect")
def test_postgres_check_executes_read_only_probe(connect: MagicMock) -> None:
    connection = connect.return_value.__enter__.return_value
    connection.execute.return_value.fetchone.return_value = (1,)

    settings = PostgresSettings()
    check_postgres(settings)

    connect.assert_called_once_with(
        host="localhost",
        port=5432,
        dbname="k12hub",
        user="k12hub",
        password="k12hub_local_only",
        connect_timeout=5,
    )
    connection.execute.assert_called_once_with("SELECT %s", (1,))


@patch("k12hub.service_checks.psycopg.connect", side_effect=OperationalError("unavailable"))
def test_postgres_check_wraps_connection_errors(connect: MagicMock) -> None:
    with pytest.raises(ServiceCheckError, match="PostgreSQL connectivity check failed"):
        check_postgres(PostgresSettings())

    connect.assert_called_once()


@patch("k12hub.service_checks.Minio")
def test_minio_check_requires_all_buckets(minio_class: MagicMock) -> None:
    client = minio_class.return_value
    client.bucket_exists.side_effect = [True, True, False]

    with pytest.raises(ServiceCheckError, match="k12-quarantine"):
        check_minio(MinioSettings())


@patch("k12hub.service_checks.Minio")
def test_minio_check_wraps_client_errors(minio_class: MagicMock) -> None:
    client = minio_class.return_value
    client.bucket_exists.side_effect = S3Error(
        code="AccessDenied",
        message="denied",
        resource="/",
        request_id="request",
        host_id="host",
        response=MagicMock(),
    )

    with pytest.raises(ServiceCheckError, match="MinIO connectivity check failed"):
        check_minio(MinioSettings())

import pytest

from k12hub.config import load_settings
from k12hub.service_checks import check_minio, check_postgres

pytestmark = pytest.mark.integration


def test_postgres_accepts_configured_connection() -> None:
    settings = load_settings({})

    assert settings.postgres.database == "k12hub"
    check_postgres(settings.postgres)


def test_minio_contains_required_buckets() -> None:
    settings = load_settings({})

    assert settings.minio.buckets == (
        "k12-raw",
        "k12-standardized",
        "k12-quarantine",
    )
    check_minio(settings.minio)

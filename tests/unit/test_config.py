from pathlib import Path

import pytest

from k12hub.config import ConfigurationError, Environment, load_settings


def test_local_settings_use_safe_defaults() -> None:
    settings = load_settings({})

    assert settings.environment is Environment.LOCAL
    assert settings.log_level == "INFO"
    assert settings.data_dir == Path("data")
    assert settings.structured_logging is True
    assert settings.postgres.database == "k12hub"
    assert settings.postgres.password == "k12hub_local_only"
    assert settings.minio.buckets == (
        "k12-raw",
        "k12-standardized",
        "k12-quarantine",
    )


def test_test_environment_uses_fixture_data_by_default() -> None:
    settings = load_settings({"K12HUB_ENV": "test"})

    assert settings.environment is Environment.TEST
    assert settings.data_dir == Path("data/fixtures")


def test_environment_values_override_defaults() -> None:
    settings = load_settings(
        {
            "K12HUB_ENV": "test",
            "K12HUB_LOG_LEVEL": "debug",
            "K12HUB_DATA_DIR": "/tmp/k12hub-tests",
            "K12HUB_STRUCTURED_LOGGING": "false",
            "POSTGRES_HOST": "postgres.test",
            "POSTGRES_PORT": "55432",
            "POSTGRES_DB": "test_hub",
            "POSTGRES_USER": "test_user",
            "POSTGRES_PASSWORD": "synthetic_test_password",
            "MINIO_ENDPOINT": "minio.test:19000",
            "MINIO_ROOT_USER": "test_access_key",
            "MINIO_ROOT_PASSWORD": "synthetic_test_secret",
            "MINIO_SECURE": "true",
            "MINIO_RAW_BUCKET": "test-raw",
            "MINIO_STANDARDIZED_BUCKET": "test-standardized",
            "MINIO_QUARANTINE_BUCKET": "test-quarantine",
        }
    )

    assert settings.log_level == "DEBUG"
    assert settings.data_dir == Path("/tmp/k12hub-tests")
    assert settings.structured_logging is False
    assert settings.postgres.host == "postgres.test"
    assert settings.postgres.port == 55432
    assert settings.postgres.database == "test_hub"
    assert settings.postgres.user == "test_user"
    assert settings.postgres.password == "synthetic_test_password"
    assert settings.minio.endpoint == "minio.test:19000"
    assert settings.minio.access_key == "test_access_key"
    assert settings.minio.secret_key == "synthetic_test_secret"
    assert settings.minio.secure is True
    assert settings.minio.buckets == (
        "test-raw",
        "test-standardized",
        "test-quarantine",
    )


def test_production_requires_explicit_data_directory() -> None:
    with pytest.raises(
        ConfigurationError,
        match="K12HUB_DATA_DIR is required when K12HUB_ENV=production",
    ):
        load_settings({"K12HUB_ENV": "production"})


@pytest.mark.parametrize("value", ["staging", "", "TESTING"])
def test_invalid_environment_fails_clearly(value: str) -> None:
    with pytest.raises(ConfigurationError, match="K12HUB_ENV must be one of"):
        load_settings({"K12HUB_ENV": value})


def test_invalid_log_level_fails_clearly() -> None:
    with pytest.raises(ConfigurationError, match="K12HUB_LOG_LEVEL is invalid"):
        load_settings({"K12HUB_LOG_LEVEL": "verbose"})


def test_invalid_boolean_fails_clearly() -> None:
    with pytest.raises(ConfigurationError, match="must be true or false"):
        load_settings({"K12HUB_STRUCTURED_LOGGING": "sometimes"})


@pytest.mark.parametrize("value", ["not-a-port", "0", "65536"])
def test_invalid_postgres_port_fails_clearly(value: str) -> None:
    with pytest.raises(ConfigurationError, match="POSTGRES_PORT"):
        load_settings({"POSTGRES_PORT": value})

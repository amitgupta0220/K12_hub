from pathlib import Path

import pytest

from k12hub.config import ConfigurationError, Environment, load_settings


def test_local_settings_use_safe_defaults() -> None:
    settings = load_settings({})

    assert settings.environment is Environment.LOCAL
    assert settings.log_level == "INFO"
    assert settings.data_dir == Path("data")
    assert settings.structured_logging is True


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
        }
    )

    assert settings.log_level == "DEBUG"
    assert settings.data_dir == Path("/tmp/k12hub-tests")
    assert settings.structured_logging is False


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

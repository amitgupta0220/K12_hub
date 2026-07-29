"""Environment-based application configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    """Raised when application configuration is invalid or incomplete."""


class Environment(str, Enum):
    """Supported runtime environments."""

    LOCAL = "local"
    TEST = "test"
    PRODUCTION = "production"


@dataclass(frozen=True)
class PostgresSettings:
    """PostgreSQL connection settings for local infrastructure checks."""

    host: str = "localhost"
    port: int = 5432
    database: str = "k12hub"
    user: str = "k12hub"
    password: str = "k12hub_local_only"


@dataclass(frozen=True)
class MinioSettings:
    """MinIO connection and bucket settings for local infrastructure checks."""

    endpoint: str = "localhost:9000"
    access_key: str = "k12hub"
    secret_key: str = "minio_local_only_change_me"
    secure: bool = False
    raw_bucket: str = "k12-raw"
    standardized_bucket: str = "k12-standardized"
    quarantine_bucket: str = "k12-quarantine"

    @property
    def buckets(self) -> tuple[str, str, str]:
        """Return all required buckets in a stable order."""

        return (
            self.raw_bucket,
            self.standardized_bucket,
            self.quarantine_bucket,
        )


@dataclass(frozen=True)
class Settings:
    """Validated application settings."""

    environment: Environment
    log_level: str
    data_dir: Path
    structured_logging: bool
    postgres: PostgresSettings = field(default_factory=PostgresSettings)
    minio: MinioSettings = field(default_factory=MinioSettings)


def _parse_environment(value: str) -> Environment:
    try:
        return Environment(value.lower())
    except ValueError as error:
        allowed = ", ".join(environment.value for environment in Environment)
        raise ConfigurationError(
            f"K12HUB_ENV must be one of: {allowed}; received {value!r}"
        ) from error


def _parse_log_level(value: str) -> str:
    normalized = value.upper()
    valid_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
    if normalized not in valid_levels:
        raise ConfigurationError(f"K12HUB_LOG_LEVEL is invalid: {value!r}")
    return normalized


def _parse_bool(name: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be true or false; received {value!r}")


def _parse_port(name: str, value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an integer; received {value!r}") from error
    if not 1 <= port <= 65535:
        raise ConfigurationError(f"{name} must be between 1 and 65535; received {value!r}")
    return port


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Load and validate settings from environment variables.

    A supplied mapping is useful for deterministic tests. When no mapping is
    supplied, values from a local ``.env`` file are loaded without overriding
    values already present in the process environment.
    """

    if environ is None:
        load_dotenv(override=False)
        values: Mapping[str, str] = os.environ
    else:
        values = environ

    environment = _parse_environment(values.get("K12HUB_ENV", Environment.LOCAL.value))
    log_level = _parse_log_level(values.get("K12HUB_LOG_LEVEL", "INFO"))
    structured_logging = _parse_bool(
        "K12HUB_STRUCTURED_LOGGING",
        values.get("K12HUB_STRUCTURED_LOGGING", "true"),
    )

    configured_data_dir = values.get("K12HUB_DATA_DIR")
    if environment is Environment.PRODUCTION and not configured_data_dir:
        raise ConfigurationError("K12HUB_DATA_DIR is required when K12HUB_ENV=production")

    default_data_dir = "data/fixtures" if environment is Environment.TEST else "data"
    data_dir = Path(configured_data_dir or default_data_dir)

    postgres = PostgresSettings(
        host=values.get("POSTGRES_HOST", "localhost"),
        port=_parse_port("POSTGRES_PORT", values.get("POSTGRES_PORT", "5432")),
        database=values.get("POSTGRES_DB", "k12hub"),
        user=values.get("POSTGRES_USER", "k12hub"),
        password=values.get("POSTGRES_PASSWORD", "k12hub_local_only"),
    )
    minio = MinioSettings(
        endpoint=values.get("MINIO_ENDPOINT", "localhost:9000"),
        access_key=values.get("MINIO_ROOT_USER", "k12hub"),
        secret_key=values.get("MINIO_ROOT_PASSWORD", "minio_local_only_change_me"),
        secure=_parse_bool("MINIO_SECURE", values.get("MINIO_SECURE", "false")),
        raw_bucket=values.get("MINIO_RAW_BUCKET", "k12-raw"),
        standardized_bucket=values.get("MINIO_STANDARDIZED_BUCKET", "k12-standardized"),
        quarantine_bucket=values.get("MINIO_QUARANTINE_BUCKET", "k12-quarantine"),
    )

    return Settings(
        environment=environment,
        log_level=log_level,
        data_dir=data_dir,
        structured_logging=structured_logging,
        postgres=postgres,
        minio=minio,
    )

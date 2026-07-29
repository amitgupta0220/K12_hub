"""Database connection and transaction utilities."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import URL, Connection, Engine, create_engine

from k12hub.config import PostgresSettings, load_settings


def build_database_url(settings: PostgresSettings) -> URL:
    """Build a safely encoded SQLAlchemy URL from PostgreSQL settings."""

    return URL.create(
        drivername="postgresql+psycopg",
        username=settings.user,
        password=settings.password,
        host=settings.host,
        port=settings.port,
        database=settings.database,
    )


def create_database_engine(settings: PostgresSettings | None = None) -> Engine:
    """Create a PostgreSQL engine with stale-connection detection."""

    resolved_settings = settings or load_settings().postgres
    return create_engine(build_database_url(resolved_settings), pool_pre_ping=True)


@contextmanager
def transaction(
    engine: Engine | None = None,
    settings: PostgresSettings | None = None,
) -> Iterator[Connection]:
    """Yield a transaction that commits on success and rolls back on failure."""

    owns_engine = engine is None
    resolved_engine = engine or create_database_engine(settings)
    try:
        with resolved_engine.begin() as connection:
            yield connection
    finally:
        if owns_engine:
            resolved_engine.dispose()

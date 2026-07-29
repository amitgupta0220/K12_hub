from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Engine

from k12hub.config import PostgresSettings
from k12hub.database import build_database_url, create_database_engine, transaction


def test_build_database_url_encodes_connection_settings() -> None:
    url = build_database_url(
        PostgresSettings(
            host="database.test",
            port=55432,
            database="test_hub",
            user="test_user",
            password="test/password",
        )
    )

    assert url.drivername == "postgresql+psycopg"
    assert url.host == "database.test"
    assert url.port == 55432
    assert url.database == "test_hub"
    assert url.username == "test_user"
    assert url.password == "test/password"


@patch("k12hub.database.create_engine")
def test_create_database_engine_enables_connection_preflight(create_engine: MagicMock) -> None:
    settings = PostgresSettings()

    result = create_database_engine(settings)

    assert result is create_engine.return_value
    create_engine.assert_called_once_with(build_database_url(settings), pool_pre_ping=True)


def test_transaction_uses_engine_context_manager() -> None:
    engine = MagicMock(spec=Engine)
    connection = engine.begin.return_value.__enter__.return_value

    with transaction(engine=engine) as yielded:
        assert yielded is connection

    engine.begin.assert_called_once_with()
    engine.begin.return_value.__exit__.assert_called_once_with(None, None, None)
    engine.dispose.assert_not_called()


def test_transaction_propagates_errors_for_rollback() -> None:
    engine = MagicMock(spec=Engine)
    error = RuntimeError("operation failed")

    with pytest.raises(RuntimeError, match="operation failed"), transaction(engine=engine):
        raise error

    exit_args = engine.begin.return_value.__exit__.call_args.args
    assert exit_args[0] is RuntimeError
    assert exit_args[1] is error

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy import inspect

from k12hub.config import PostgresSettings, load_settings
from k12hub.database import create_database_engine

pytestmark = [pytest.mark.integration, pytest.mark.migration]

EXPECTED_TABLES = {
    "metadata": {"source_system", "data_contract", "data_quality_rule"},
    "audit": {
        "pipeline_run",
        "source_file",
        "row_count_reconciliation",
        "access_event",
        "data_quality_rule_run",
        "data_quality_rule_result",
        "data_quality_failure",
    },
    "quarantine": {"rejected_record"},
    "staging": {
        "sis_student",
        "sis_enrollment",
        "attendance_event",
        "assessment_event",
    },
}
EXPECTED_EMPTY_SCHEMAS = {"raw", "core", "mart"}


def _alembic_config() -> Config:
    return Config("alembic.ini")


def _assert_expected_database_objects(settings: PostgresSettings) -> None:
    engine = create_database_engine(settings)
    try:
        inspector = inspect(engine)
        schemas = set(inspector.get_schema_names())
        assert set(EXPECTED_TABLES) | EXPECTED_EMPTY_SCHEMAS <= schemas

        for schema, expected_tables in EXPECTED_TABLES.items():
            assert set(inspector.get_table_names(schema=schema)) == expected_tables

        for schema in EXPECTED_EMPTY_SCHEMAS:
            assert inspector.get_table_names(schema=schema) == []

        pipeline_columns = {
            column["name"] for column in inspector.get_columns("pipeline_run", schema="audit")
        }
        assert {
            "pipeline_run_id",
            "pipeline_name",
            "started_at",
            "finished_at",
            "status",
            "records_discovered",
            "records_loaded",
            "records_rejected",
            "error_message",
        } <= pipeline_columns

        source_file_columns = {
            column["name"] for column in inspector.get_columns("source_file", schema="audit")
        }
        assert {
            "source_file_id",
            "pipeline_run_id",
            "source_system",
            "original_filename",
            "object_path",
            "sha256_checksum",
            "file_size_bytes",
            "discovered_at",
            "loaded_at",
            "status",
            "row_count",
        } <= source_file_columns

        rejected_columns = {
            column["name"]
            for column in inspector.get_columns("rejected_record", schema="quarantine")
        }
        assert {
            "rejected_record_id",
            "pipeline_run_id",
            "source_file_id",
            "source_system",
            "source_row_number",
            "rule_id",
            "severity",
            "error_message",
            "raw_payload",
            "detected_at",
            "resolution_status",
        } <= rejected_columns

        reconciliation_columns = {
            column["name"]
            for column in inspector.get_columns(
                "row_count_reconciliation",
                schema="audit",
            )
        }
        assert {
            "discovered_row_count",
            "parsed_row_count",
            "loaded_row_count",
            "rejected_row_count",
        } <= reconciliation_columns

        required_staging_columns = {
            "pipeline_run_id",
            "source_file_id",
            "source_row_number",
            "source_schema_version",
            "ingested_at",
            "raw_payload",
        }
        for table_name in EXPECTED_TABLES["staging"]:
            staging_columns = {
                column["name"] for column in inspector.get_columns(table_name, schema="staging")
            }
            assert required_staging_columns <= staging_columns

        rule_columns = {
            column["name"]
            for column in inspector.get_columns("data_quality_rule", schema="metadata")
        }
        assert {"dataset", "blocking", "remediation_guidance"} <= rule_columns

        quality_failure_columns = {
            column["name"]
            for column in inspector.get_columns("data_quality_failure", schema="audit")
        }
        assert {
            "data_quality_rule_run_id",
            "pipeline_run_id",
            "source_file_id",
            "source_row_number",
            "rule_id",
            "rule_code",
            "severity",
            "blocking",
            "message",
            "remediation_guidance",
            "raw_payload",
        } <= quality_failure_columns

        assert inspector.get_indexes("pipeline_run", schema="audit")
        assert inspector.get_indexes("source_file", schema="audit")
        assert inspector.get_indexes("rejected_record", schema="quarantine")
    finally:
        engine.dispose()


@pytest.fixture
def clean_migration_database(monkeypatch: pytest.MonkeyPatch) -> Iterator[PostgresSettings]:
    base_settings = load_settings({}).postgres
    database_name = f"k12hub_migration_{uuid4().hex[:12]}"

    with psycopg.connect(
        host=base_settings.host,
        port=base_settings.port,
        dbname=base_settings.database,
        user=base_settings.user,
        password=base_settings.password,
        autocommit=True,
    ) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))

    monkeypatch.setenv("POSTGRES_DB", database_name)
    test_settings = PostgresSettings(
        host=base_settings.host,
        port=base_settings.port,
        database=database_name,
        user=base_settings.user,
        password=base_settings.password,
    )

    try:
        yield test_settings
    finally:
        with psycopg.connect(
            host=base_settings.host,
            port=base_settings.port,
            dbname=base_settings.database,
            user=base_settings.user,
            password=base_settings.password,
            autocommit=True,
        ) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s",
                (database_name,),
            )
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database_name)))


def test_operational_schemas_and_tables_exist() -> None:
    _assert_expected_database_objects(load_settings({}).postgres)


def test_clean_database_accepts_full_migration_twice(
    clean_migration_database: PostgresSettings,
) -> None:
    command.upgrade(_alembic_config(), "head")
    command.upgrade(_alembic_config(), "head")

    _assert_expected_database_objects(clean_migration_database)

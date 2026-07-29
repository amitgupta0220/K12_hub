from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from minio import Minio
from sqlalchemy import Engine, text

from k12hub.cli import main
from k12hub.config import Settings, load_settings
from k12hub.contracts import load_configuration
from k12hub.database import create_database_engine, transaction
from k12hub.generator import ERROR_TYPES, GeneratorOptions, generate_data
from k12hub.ingestion import (
    IngestionResult,
    PostgresIngestionMetadataStore,
    RawFileIngestionService,
)
from k12hub.object_store import MinioObjectStorageClient
from k12hub.quality import DataQualityService, PostgresQualityStore
from k12hub.staging import PostgresStagingMetadataStore, StagingLoaderService

pytestmark = pytest.mark.integration
PIPELINE_PREFIX = "integration_quality_"


@pytest.fixture
def quality_services() -> Iterator[tuple[Settings, Engine, MinioObjectStorageClient]]:
    settings = load_settings({})
    engine = create_database_engine(settings.postgres)
    object_store = MinioObjectStorageClient(settings.minio)
    minio_client = Minio(
        settings.minio.endpoint,
        access_key=settings.minio.access_key,
        secret_key=settings.minio.secret_key,
        secure=settings.minio.secure,
    )

    def cleanup() -> None:
        with transaction(engine=engine) as connection:
            object_paths = list(
                connection.execute(
                    text(
                        """
                        SELECT source_file.object_path
                        FROM audit.source_file AS source_file
                        JOIN audit.pipeline_run AS pipeline_run
                          ON pipeline_run.pipeline_run_id = source_file.pipeline_run_id
                        WHERE pipeline_run.pipeline_name LIKE :pipeline_pattern
                        """
                    ),
                    {"pipeline_pattern": f"{PIPELINE_PREFIX}%"},
                ).scalars()
            )
            connection.execute(
                text("DELETE FROM audit.pipeline_run WHERE pipeline_name LIKE :pipeline_pattern"),
                {"pipeline_pattern": f"{PIPELINE_PREFIX}%"},
            )
        for object_path in object_paths:
            minio_client.remove_object(settings.minio.raw_bucket, object_path)

    cleanup()
    try:
        yield settings, engine, object_store
    finally:
        cleanup()
        engine.dispose()


def _ingest_and_stage(
    input_dir: Path,
    pipeline_name: str,
    settings: Settings,
    engine: Engine,
    object_store: MinioObjectStorageClient,
) -> IngestionResult:
    configuration = load_configuration()
    ingestion = RawFileIngestionService(
        PostgresIngestionMetadataStore(engine),
        object_store,
        settings.minio,
        pipeline_name=pipeline_name,
    ).ingest(input_dir, configuration)
    StagingLoaderService(
        PostgresStagingMetadataStore(engine),
        object_store,
        settings.minio,
    ).load(ingestion.pipeline_run_id, configuration)
    return ingestion


def test_clean_pipeline_persists_passing_dashboard_results(
    tmp_path: Path,
    quality_services: tuple[Settings, Engine, MinioObjectStorageClient],
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings, engine, object_store = quality_services
    generated = generate_data(GeneratorOptions(seed=8400, students=10, output_directory=tmp_path))
    ingestion = _ingest_and_stage(
        generated.output_path,
        f"{PIPELINE_PREFIX}clean",
        settings,
        engine,
        object_store,
    )

    exit_code = main(
        [
            "validate-data",
            "--pipeline-run-id",
            str(ingestion.pipeline_run_id),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "status=passed" in output
    assert "STU-001" in output
    with transaction(engine=engine) as connection:
        quality_run = connection.execute(
            text(
                """
                SELECT status, enabled_rule_count, failure_count,
                       blocking_failure_count
                FROM audit.data_quality_rule_run
                WHERE pipeline_run_id = :pipeline_run_id
                """
            ),
            {"pipeline_run_id": ingestion.pipeline_run_id},
        ).one()
        result_count = connection.execute(
            text(
                """
                SELECT count(*)
                FROM audit.data_quality_rule_result
                WHERE pipeline_run_id = :pipeline_run_id
                """
            ),
            {"pipeline_run_id": ingestion.pipeline_run_id},
        ).scalar_one()

    assert tuple(quality_run) == ("passed", 18, 0, 0)
    assert result_count == 18


def test_injected_failures_are_audited_and_blocking_rows_quarantined(
    tmp_path: Path,
    quality_services: tuple[Settings, Engine, MinioObjectStorageClient],
) -> None:
    settings, engine, object_store = quality_services
    generated = generate_data(
        GeneratorOptions(
            seed=8401,
            students=12,
            error_rate=0.1,
            enabled_error_types=ERROR_TYPES,
            output_directory=tmp_path,
        )
    )
    ingestion = _ingest_and_stage(
        generated.output_path,
        f"{PIPELINE_PREFIX}errors",
        settings,
        engine,
        object_store,
    )

    result = DataQualityService(PostgresQualityStore(engine)).validate(
        ingestion.pipeline_run_id,
        load_configuration(),
    )

    expected_failed_rules = {
        "STU-001",
        "STU-002",
        "STU-003",
        "ENR-002",
        "ENR-003",
        "ATT-001",
        "ATT-003",
        "ATT-004",
        "ATT-005",
        "ATT-007",
        "ASM-002",
        "PIPE-003",
    }
    assert result.status == "failed"
    assert {
        summary.rule_id for summary in result.rule_summaries if summary.failures
    } == expected_failed_rules
    assert result.blocking_failures == result.failures
    with transaction(engine=engine) as connection:
        failure_rows = connection.execute(
            text(
                """
                SELECT rule_code, source_row_number, severity, message,
                       remediation_guidance
                FROM audit.data_quality_failure
                WHERE data_quality_rule_run_id = :quality_run_id
                """
            ),
            {"quality_run_id": result.data_quality_rule_run_id},
        ).all()
        quarantine_count = connection.execute(
            text(
                """
                SELECT count(*)
                FROM quarantine.rejected_record
                WHERE pipeline_run_id = :pipeline_run_id
                  AND rule_code <> 'LEGACY'
                """
            ),
            {"pipeline_run_id": ingestion.pipeline_run_id},
        ).scalar_one()

    assert len(failure_rows) == result.failures
    assert quarantine_count == result.blocking_failures
    assert all(
        row.rule_code in expected_failed_rules
        and row.source_row_number >= 0
        and row.severity
        and row.message
        and row.remediation_guidance
        for row in failure_rows
    )


def test_nonblocking_row_count_failure_stays_flagged_without_quarantine(
    tmp_path: Path,
    quality_services: tuple[Settings, Engine, MinioObjectStorageClient],
) -> None:
    settings, engine, object_store = quality_services
    pipeline_name = f"{PIPELINE_PREFIX}volume"
    baseline = generate_data(
        GeneratorOptions(seed=8402, students=8, output_directory=tmp_path / "baseline")
    )
    baseline_ingestion = _ingest_and_stage(
        baseline.output_path,
        pipeline_name,
        settings,
        engine,
        object_store,
    )
    DataQualityService(PostgresQualityStore(engine)).validate(
        baseline_ingestion.pipeline_run_id,
        load_configuration(),
    )
    changed = generate_data(
        GeneratorOptions(seed=8403, students=16, output_directory=tmp_path / "changed")
    )
    changed_ingestion = _ingest_and_stage(
        changed.output_path,
        pipeline_name,
        settings,
        engine,
        object_store,
    )

    result = DataQualityService(PostgresQualityStore(engine)).validate(
        changed_ingestion.pipeline_run_id,
        load_configuration(),
    )

    pipe_summary = next(
        summary for summary in result.rule_summaries if summary.rule_id == "PIPE-001"
    )
    assert result.status == "passed"
    assert result.failures == pipe_summary.failures
    assert result.blocking_failures == 0
    assert pipe_summary.failures == 4
    with transaction(engine=engine) as connection:
        audit_count = connection.execute(
            text(
                """
                SELECT count(*)
                FROM audit.data_quality_failure
                WHERE data_quality_rule_run_id = :quality_run_id
                  AND rule_code = 'PIPE-001'
                """
            ),
            {"quality_run_id": result.data_quality_rule_run_id},
        ).scalar_one()
        quarantine_count = connection.execute(
            text(
                """
                SELECT count(*)
                FROM quarantine.rejected_record
                WHERE pipeline_run_id = :pipeline_run_id
                  AND rule_code = 'PIPE-001'
                """
            ),
            {"pipeline_run_id": changed_ingestion.pipeline_run_id},
        ).scalar_one()

    assert audit_count == 4
    assert quarantine_count == 0

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from minio import Minio
from sqlalchemy import Connection, Engine, text

from k12hub.config import Settings, load_settings
from k12hub.contracts import load_configuration
from k12hub.database import create_database_engine, transaction
from k12hub.generator import GeneratorOptions, generate_data
from k12hub.ingestion import (
    IngestionResult,
    PostgresIngestionMetadataStore,
    RawFileIngestionService,
)
from k12hub.object_store import MinioObjectStorageClient
from k12hub.staging import (
    PostgresStagingMetadataStore,
    SourceFileReference,
    StagingLoaderService,
    parse_object,
)

pytestmark = pytest.mark.integration
PIPELINE_PREFIX = "integration_staging_"


@pytest.fixture
def staging_services() -> Iterator[tuple[Settings, Engine, MinioObjectStorageClient]]:
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


def _ingest(
    input_dir: Path,
    pipeline_name: str,
    settings: Settings,
    engine: Engine,
    object_store: MinioObjectStorageClient,
) -> IngestionResult:
    return RawFileIngestionService(
        PostgresIngestionMetadataStore(engine),
        object_store,
        settings.minio,
        pipeline_name=pipeline_name,
    ).ingest(input_dir, load_configuration())


def test_every_format_loads_and_retry_is_idempotent(
    tmp_path: Path,
    staging_services: tuple[Settings, Engine, MinioObjectStorageClient],
) -> None:
    settings, engine, object_store = staging_services
    input_dir = generate_data(
        GeneratorOptions(seed=7010, students=6, output_directory=tmp_path)
    ).output_path
    manifest = json.loads((input_dir / "generation_manifest.json").read_text(encoding="utf-8"))
    ingestion = _ingest(
        input_dir,
        f"{PIPELINE_PREFIX}formats",
        settings,
        engine,
        object_store,
    )
    service = StagingLoaderService(
        PostgresStagingMetadataStore(engine, batch_size=2),
        object_store,
        settings.minio,
    )

    first = service.load(ingestion.pipeline_run_id, load_configuration())
    second = service.load(ingestion.pipeline_run_id, load_configuration())

    expected_total = sum(manifest["record_counts"].values())
    assert first.discovered == expected_total
    assert first.loaded == expected_total
    assert first.rejected == 0
    assert second == first
    with transaction(engine=engine) as connection:
        table_counts = {
            table_name: connection.execute(
                text(
                    f"""
                    SELECT count(*)
                    FROM staging.{table_name}
                    WHERE pipeline_run_id = :pipeline_run_id
                    """
                ),
                {"pipeline_run_id": ingestion.pipeline_run_id},
            ).scalar_one()
            for table_name in (
                "sis_student",
                "sis_enrollment",
                "attendance_event",
                "assessment_event",
            )
        }
        reconciliations = connection.execute(
            text(
                """
                SELECT discovered_row_count, parsed_row_count,
                       loaded_row_count, rejected_row_count, status
                FROM audit.row_count_reconciliation
                WHERE pipeline_run_id = :pipeline_run_id
                """
            ),
            {"pipeline_run_id": ingestion.pipeline_run_id},
        ).all()

    assert table_counts == {
        "sis_student": manifest["record_counts"]["students.csv"],
        "sis_enrollment": manifest["record_counts"]["enrollments.csv"],
        "attendance_event": manifest["record_counts"]["attendance_events.jsonl"],
        "assessment_event": manifest["record_counts"]["assessments.xlsx"],
    }
    assert len(reconciliations) == 4
    assert all(
        row.discovered_row_count == row.parsed_row_count + row.rejected_row_count
        and row.loaded_row_count == row.parsed_row_count
        and row.status == "matched"
        for row in reconciliations
    )


def test_three_malformed_rows_are_quarantined_and_reconciled(
    tmp_path: Path,
    staging_services: tuple[Settings, Engine, MinioObjectStorageClient],
) -> None:
    settings, engine, object_store = staging_services
    input_dir = generate_data(
        GeneratorOptions(seed=7011, students=100, output_directory=tmp_path)
    ).output_path
    source = io.StringIO((input_dir / "students.csv").read_text(encoding="utf-8"))
    rows = list(csv.reader(source))
    birth_date_index = rows[0].index("birth_date")
    for row in rows[1:4]:
        row[birth_date_index] = "malformed-date"
    output = io.StringIO()
    csv.writer(output, lineterminator="\n").writerows(rows)
    (input_dir / "students.csv").write_text(output.getvalue(), encoding="utf-8")
    ingestion = _ingest(
        input_dir,
        f"{PIPELINE_PREFIX}malformed",
        settings,
        engine,
        object_store,
    )

    StagingLoaderService(
        PostgresStagingMetadataStore(engine),
        object_store,
        settings.minio,
    ).load(ingestion.pipeline_run_id, load_configuration())

    with transaction(engine=engine) as connection:
        reconciliation = connection.execute(
            text(
                """
                SELECT reconciliation.discovered_row_count,
                       reconciliation.parsed_row_count,
                       reconciliation.loaded_row_count,
                       reconciliation.rejected_row_count,
                       reconciliation.status
                FROM audit.row_count_reconciliation AS reconciliation
                JOIN audit.source_file AS source_file
                  ON source_file.source_file_id = reconciliation.source_file_id
                WHERE reconciliation.pipeline_run_id = :pipeline_run_id
                  AND source_file.original_filename = 'students.csv'
                """
            ),
            {"pipeline_run_id": ingestion.pipeline_run_id},
        ).one()

    assert reconciliation.discovered_row_count == 100
    assert reconciliation.parsed_row_count == 97
    assert reconciliation.loaded_row_count == 97
    assert reconciliation.rejected_row_count == 3
    assert reconciliation.status == "matched"


class FailingStagingStore(PostgresStagingMetadataStore):
    def _before_reconciliation(
        self,
        connection: Connection,
        source_file: SourceFileReference,
    ) -> None:
        raise RuntimeError("forced transaction rollback")


def test_file_load_rolls_back_all_rows_on_failure(
    tmp_path: Path,
    staging_services: tuple[Settings, Engine, MinioObjectStorageClient],
) -> None:
    settings, engine, object_store = staging_services
    input_dir = generate_data(
        GeneratorOptions(seed=7012, students=2, output_directory=tmp_path)
    ).output_path
    ingestion = _ingest(
        input_dir,
        f"{PIPELINE_PREFIX}rollback",
        settings,
        engine,
        object_store,
    )
    store = FailingStagingStore(engine)
    source_file = next(
        item
        for item in store.list_loaded_source_files(ingestion.pipeline_run_id)
        if item.original_filename == "students.csv"
    )
    contract = load_configuration().contracts["sis_students"]
    parsed = parse_object(
        object_store.read_object(settings.minio.raw_bucket, source_file.object_path),
        contract,
    )

    with pytest.raises(RuntimeError, match="forced transaction rollback"):
        store.load_file(source_file, contract, parsed)

    with transaction(engine=engine) as connection:
        staging_count = connection.execute(
            text("SELECT count(*) FROM staging.sis_student WHERE source_file_id = :id"),
            {"id": source_file.source_file_id},
        ).scalar_one()
        quarantine_count = connection.execute(
            text("SELECT count(*) FROM quarantine.rejected_record WHERE source_file_id = :id"),
            {"id": source_file.source_file_id},
        ).scalar_one()
        reconciliation_count = connection.execute(
            text("SELECT count(*) FROM audit.row_count_reconciliation WHERE source_file_id = :id"),
            {"id": source_file.source_file_id},
        ).scalar_one()
        row_count = connection.execute(
            text("SELECT row_count FROM audit.source_file WHERE source_file_id = :id"),
            {"id": source_file.source_file_id},
        ).scalar_one()

    assert (staging_count, quarantine_count, reconciliation_count, row_count) == (0, 0, 0, None)

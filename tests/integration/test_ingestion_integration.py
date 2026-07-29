from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from minio import Minio
from sqlalchemy import Engine, text

from k12hub.config import Settings, load_settings
from k12hub.contracts import load_configuration
from k12hub.database import create_database_engine, transaction
from k12hub.generator import GeneratorOptions, generate_data
from k12hub.ingestion import PostgresIngestionMetadataStore, RawFileIngestionService
from k12hub.object_store import MinioObjectStorageClient

pytestmark = pytest.mark.integration
PIPELINE_NAME = "integration_raw_file_ingestion"


@pytest.fixture
def ingestion_services() -> Iterator[tuple[Settings, Engine]]:
    settings = load_settings({})
    engine = create_database_engine(settings.postgres)
    minio_client = Minio(
        settings.minio.endpoint,
        access_key=settings.minio.access_key,
        secret_key=settings.minio.secret_key,
        secure=settings.minio.secure,
    )

    with transaction(engine=engine) as connection:
        existing_object_paths = connection.execute(
            text(
                """
                SELECT source_file.object_path
                FROM audit.source_file AS source_file
                JOIN audit.pipeline_run AS pipeline_run
                  ON pipeline_run.pipeline_run_id = source_file.pipeline_run_id
                WHERE pipeline_run.pipeline_name = :pipeline_name
                """
            ),
            {"pipeline_name": PIPELINE_NAME},
        ).scalars()
        for object_path in existing_object_paths:
            minio_client.remove_object(settings.minio.raw_bucket, object_path)
        connection.execute(
            text("DELETE FROM audit.pipeline_run WHERE pipeline_name = :pipeline_name"),
            {"pipeline_name": PIPELINE_NAME},
        )

    try:
        yield settings, engine
    finally:
        with transaction(engine=engine) as connection:
            cleanup_object_paths = list(
                connection.execute(
                    text(
                        """
                        SELECT source_file.object_path
                        FROM audit.source_file AS source_file
                        JOIN audit.pipeline_run AS pipeline_run
                          ON pipeline_run.pipeline_run_id = source_file.pipeline_run_id
                        WHERE pipeline_run.pipeline_name = :pipeline_name
                        """
                    ),
                    {"pipeline_name": PIPELINE_NAME},
                ).scalars()
            )
            connection.execute(
                text("DELETE FROM audit.pipeline_run WHERE pipeline_name = :pipeline_name"),
                {"pipeline_name": PIPELINE_NAME},
            )
        for object_path in cleanup_object_paths:
            minio_client.remove_object(settings.minio.raw_bucket, object_path)
        engine.dispose()


def test_minio_and_postgres_ingestion_is_idempotent(
    tmp_path: Path,
    ingestion_services: tuple[Settings, Engine],
) -> None:
    settings, engine = ingestion_services
    input_dir = generate_data(
        GeneratorOptions(
            seed=6006,
            students=6,
            output_directory=tmp_path,
        )
    ).output_path
    service = RawFileIngestionService(
        PostgresIngestionMetadataStore(engine),
        MinioObjectStorageClient(settings.minio),
        settings.minio,
        pipeline_name=PIPELINE_NAME,
    )

    first = service.ingest(input_dir, load_configuration())
    second = service.ingest(input_dir, load_configuration())

    assert first.uploaded == 4
    assert second.uploaded == 0
    assert second.skipped == 4
    with transaction(engine=engine) as connection:
        source_file_count = connection.execute(
            text(
                """
                SELECT count(*)
                FROM audit.source_file AS source_file
                JOIN audit.pipeline_run AS pipeline_run
                  ON pipeline_run.pipeline_run_id = source_file.pipeline_run_id
                WHERE pipeline_run.pipeline_name = :pipeline_name
                """
            ),
            {"pipeline_name": PIPELINE_NAME},
        ).scalar_one()
        run_count_rows = connection.execute(
            text(
                """
                SELECT records_loaded, status
                FROM audit.pipeline_run
                WHERE pipeline_run_id IN (:first_run, :second_run)
                ORDER BY started_at
                """
            ),
            {
                "first_run": first.pipeline_run_id,
                "second_run": second.pipeline_run_id,
            },
        ).all()

    assert source_file_count == 4
    assert [(row.records_loaded, row.status) for row in run_count_rows] == [
        (4, "completed"),
        (0, "completed"),
    ]

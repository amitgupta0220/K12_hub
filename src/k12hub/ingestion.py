"""Idempotent raw-file ingestion with transactional audit metadata."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import UUID

from sqlalchemy import Engine, text

from k12hub.checksums import sha256_file
from k12hub.config import MinioSettings
from k12hub.contracts import ConfigurationBundle, SourceSystem
from k12hub.database import transaction
from k12hub.discovery import (
    DiscoveredSourceFile,
    discover_source_files,
    load_generation_context,
)
from k12hub.object_store import ObjectStorageClient

LOGGER = logging.getLogger(__name__)
UNAVAILABLE_CHECKSUM = "0" * 64


class IngestionError(RuntimeError):
    """Raised when an ingestion run cannot complete its audit lifecycle."""


@dataclass(frozen=True)
class SourceFileAudit:
    """Metadata recorded before an upload begins."""

    pipeline_run_id: UUID
    source_system: str
    original_filename: str
    object_path: str
    sha256_checksum: str
    file_size_bytes: int


@dataclass(frozen=True)
class IngestionResult:
    """Counts and identity for one completed ingestion attempt."""

    pipeline_run_id: UUID
    status: str
    discovered: int
    uploaded: int
    skipped: int
    failed: int


class IngestionMetadataStore(Protocol):
    """Transactional metadata operations required by ingestion."""

    def register_source_systems(self, source_systems: Iterable[SourceSystem]) -> None:
        """Ensure configured source systems exist for audit foreign keys."""

    def create_pipeline_run(self, pipeline_name: str) -> UUID:
        """Create and return a running pipeline audit record."""

    def checksum_was_loaded(self, source_system: str, checksum: str) -> bool:
        """Return whether this exact source content was loaded previously."""

    def create_source_file(self, source_file: SourceFileAudit) -> UUID:
        """Create a discovered source-file audit record."""

    def mark_source_file_loaded(self, source_file_id: UUID) -> None:
        """Mark an uploaded source file as loaded."""

    def mark_source_file_failed(self, source_file_id: UUID) -> None:
        """Mark a source file as failed while preserving its metadata."""

    def finish_pipeline_run(
        self,
        pipeline_run_id: UUID,
        *,
        status: str,
        discovered: int,
        loaded: int,
        failed: int,
        error_message: str | None,
    ) -> None:
        """Finish the run and record aggregate file counts."""


class PostgresIngestionMetadataStore:
    """PostgreSQL implementation with one transaction per audit operation."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def register_source_systems(self, source_systems: Iterable[SourceSystem]) -> None:
        statement = text(
            """
            INSERT INTO metadata.source_system (
                source_system_code, name, description, data_category
            )
            VALUES (:code, :name, :description, :data_category)
            ON CONFLICT (source_system_code) DO NOTHING
            """
        )
        with transaction(engine=self._engine) as connection:
            for source_system in source_systems:
                connection.execute(
                    statement,
                    {
                        "code": source_system.name,
                        "name": source_system.name,
                        "description": source_system.description,
                        "data_category": source_system.data_category.value,
                    },
                )

    def create_pipeline_run(self, pipeline_name: str) -> UUID:
        with transaction(engine=self._engine) as connection:
            pipeline_run_id = connection.execute(
                text(
                    """
                    INSERT INTO audit.pipeline_run (pipeline_name, status)
                    VALUES (:pipeline_name, 'running')
                    RETURNING pipeline_run_id
                    """
                ),
                {"pipeline_name": pipeline_name},
            ).scalar_one()
        return UUID(str(pipeline_run_id))

    def checksum_was_loaded(self, source_system: str, checksum: str) -> bool:
        with transaction(engine=self._engine) as connection:
            result = connection.execute(
                text(
                    """
                    SELECT 1
                    FROM audit.source_file
                    WHERE source_system = :source_system
                      AND sha256_checksum = :checksum
                      AND status = 'loaded'
                    LIMIT 1
                    """
                ),
                {"source_system": source_system, "checksum": checksum},
            ).first()
        return result is not None

    def create_source_file(self, source_file: SourceFileAudit) -> UUID:
        with transaction(engine=self._engine) as connection:
            source_file_id = connection.execute(
                text(
                    """
                    INSERT INTO audit.source_file (
                        pipeline_run_id,
                        source_system,
                        original_filename,
                        object_path,
                        sha256_checksum,
                        file_size_bytes,
                        status
                    )
                    VALUES (
                        :pipeline_run_id,
                        :source_system,
                        :original_filename,
                        :object_path,
                        :sha256_checksum,
                        :file_size_bytes,
                        'discovered'
                    )
                    RETURNING source_file_id
                    """
                ),
                {
                    "pipeline_run_id": source_file.pipeline_run_id,
                    "source_system": source_file.source_system,
                    "original_filename": source_file.original_filename,
                    "object_path": source_file.object_path,
                    "sha256_checksum": source_file.sha256_checksum,
                    "file_size_bytes": source_file.file_size_bytes,
                },
            ).scalar_one()
        return UUID(str(source_file_id))

    def mark_source_file_loaded(self, source_file_id: UUID) -> None:
        with transaction(engine=self._engine) as connection:
            connection.execute(
                text(
                    """
                    UPDATE audit.source_file
                    SET status = 'loaded',
                        loaded_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE source_file_id = :source_file_id
                    """
                ),
                {"source_file_id": source_file_id},
            )

    def mark_source_file_failed(self, source_file_id: UUID) -> None:
        with transaction(engine=self._engine) as connection:
            connection.execute(
                text(
                    """
                    UPDATE audit.source_file
                    SET status = 'failed',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE source_file_id = :source_file_id
                    """
                ),
                {"source_file_id": source_file_id},
            )

    def finish_pipeline_run(
        self,
        pipeline_run_id: UUID,
        *,
        status: str,
        discovered: int,
        loaded: int,
        failed: int,
        error_message: str | None,
    ) -> None:
        with transaction(engine=self._engine) as connection:
            connection.execute(
                text(
                    """
                    UPDATE audit.pipeline_run
                    SET finished_at = CURRENT_TIMESTAMP,
                        status = :status,
                        records_discovered = :discovered,
                        records_loaded = :loaded,
                        records_rejected = :failed,
                        error_message = :error_message,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE pipeline_run_id = :pipeline_run_id
                    """
                ),
                {
                    "pipeline_run_id": pipeline_run_id,
                    "status": status,
                    "discovered": discovered,
                    "loaded": loaded,
                    "failed": failed,
                    "error_message": error_message,
                },
            )


def _object_path(
    source_file: DiscoveredSourceFile,
    school_year: str,
    ingestion_time: datetime,
    pipeline_run_id: UUID,
) -> str:
    return "/".join(
        (
            source_file.source_system,
            school_year,
            ingestion_time.date().isoformat(),
            str(pipeline_run_id),
            source_file.filename,
        )
    )


class RawFileIngestionService:
    """Coordinate discovery, duplicate detection, upload, and audit writes."""

    def __init__(
        self,
        metadata_store: IngestionMetadataStore,
        object_store: ObjectStorageClient,
        minio_settings: MinioSettings,
        *,
        pipeline_name: str = "raw_file_ingestion",
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._metadata_store = metadata_store
        self._object_store = object_store
        self._raw_bucket = minio_settings.raw_bucket
        self._pipeline_name = pipeline_name
        self._now = now or (lambda: datetime.now(timezone.utc))

    def ingest(
        self,
        input_dir: Path,
        configuration: ConfigurationBundle,
        source: str = "all",
    ) -> IngestionResult:
        """Ingest matching raw files while preserving prior successful metadata."""

        self._metadata_store.register_source_systems(configuration.source_systems.source_systems)
        pipeline_run_id = self._metadata_store.create_pipeline_run(self._pipeline_name)
        log_context = {"pipeline_run_id": str(pipeline_run_id)}
        LOGGER.info("Raw-file ingestion started", extra=log_context)

        discovered_count = 0
        uploaded_count = 0
        skipped_count = 0
        failed_count = 0
        failure_messages: list[str] = []
        try:
            generation_context = load_generation_context(input_dir)
            discovered_files = discover_source_files(input_dir, configuration, source)
            discovered_count = len(discovered_files)

            for source_file in discovered_files:
                file_context = {
                    **log_context,
                    "source_system": source_file.source_system,
                    "source_filename": source_file.filename,
                }
                try:
                    checksum = sha256_file(source_file.path)
                except OSError:
                    object_path = _object_path(
                        source_file,
                        generation_context.school_year,
                        self._now(),
                        pipeline_run_id,
                    )
                    source_file_id = self._metadata_store.create_source_file(
                        SourceFileAudit(
                            pipeline_run_id=pipeline_run_id,
                            source_system=source_file.source_system,
                            original_filename=source_file.filename,
                            object_path=object_path,
                            sha256_checksum=UNAVAILABLE_CHECKSUM,
                            file_size_bytes=source_file.file_size_bytes,
                        )
                    )
                    self._metadata_store.mark_source_file_failed(source_file_id)
                    failed_count += 1
                    failure_messages.append(f"{source_file.filename}: checksum failed")
                    LOGGER.exception("Source-file checksum failed", extra=file_context)
                    continue

                if self._metadata_store.checksum_was_loaded(
                    source_file.source_system,
                    checksum,
                ):
                    skipped_count += 1
                    LOGGER.info("Exact duplicate source file skipped", extra=file_context)
                    continue

                object_path = _object_path(
                    source_file,
                    generation_context.school_year,
                    self._now(),
                    pipeline_run_id,
                )
                source_file_id = self._metadata_store.create_source_file(
                    SourceFileAudit(
                        pipeline_run_id=pipeline_run_id,
                        source_system=source_file.source_system,
                        original_filename=source_file.filename,
                        object_path=object_path,
                        sha256_checksum=checksum,
                        file_size_bytes=source_file.file_size_bytes,
                    )
                )
                try:
                    self._object_store.upload_file(
                        self._raw_bucket,
                        object_path,
                        source_file.path,
                    )
                    self._metadata_store.mark_source_file_loaded(source_file_id)
                except Exception:
                    self._metadata_store.mark_source_file_failed(source_file_id)
                    failed_count += 1
                    failure_messages.append(f"{source_file.filename}: upload failed")
                    LOGGER.exception("Raw source-file upload failed", extra=file_context)
                    continue

                uploaded_count += 1
                LOGGER.info("Raw source file uploaded", extra=file_context)
        except Exception as error:
            failure_messages.append(str(error))
            failed_count = max(failed_count, 1)
            status = "failed"
            self._metadata_store.finish_pipeline_run(
                pipeline_run_id,
                status=status,
                discovered=discovered_count,
                loaded=uploaded_count,
                failed=failed_count,
                error_message="; ".join(failure_messages),
            )
            LOGGER.exception("Raw-file ingestion failed", extra=log_context)
            raise IngestionError(
                f"Raw-file ingestion failed for pipeline run {pipeline_run_id}: {error}"
            ) from error

        status = "failed" if failed_count else "completed"
        self._metadata_store.finish_pipeline_run(
            pipeline_run_id,
            status=status,
            discovered=discovered_count,
            loaded=uploaded_count,
            failed=failed_count,
            error_message="; ".join(failure_messages) or None,
        )
        LOGGER.info(
            "Raw-file ingestion finished",
            extra={
                **log_context,
                "discovered": discovered_count,
                "uploaded": uploaded_count,
                "skipped": skipped_count,
                "failed": failed_count,
            },
        )
        return IngestionResult(
            pipeline_run_id=pipeline_run_id,
            status=status,
            discovered=discovered_count,
            uploaded=uploaded_count,
            skipped=skipped_count,
            failed=failed_count,
        )

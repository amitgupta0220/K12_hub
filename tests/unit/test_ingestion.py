from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest

from k12hub.checksums import sha256_file
from k12hub.config import MinioSettings
from k12hub.contracts import SourceSystem, load_configuration
from k12hub.discovery import DiscoveryError, discover_source_files, load_generation_context
from k12hub.generator import GeneratorOptions, generate_data
from k12hub.ingestion import (
    IngestionMetadataStore,
    RawFileIngestionService,
    SourceFileAudit,
)


class FakeMetadataStore(IngestionMetadataStore):
    def __init__(self) -> None:
        self.next_id = 1
        self.loaded_checksums: set[tuple[str, str]] = set()
        self.source_files: dict[UUID, tuple[SourceFileAudit, str]] = {}
        self.pipeline_runs: dict[UUID, dict[str, object]] = {}
        self.source_systems: set[str] = set()

    def _uuid(self) -> UUID:
        identifier = UUID(int=self.next_id)
        self.next_id += 1
        return identifier

    def register_source_systems(self, source_systems: Iterable[SourceSystem]) -> None:
        self.source_systems.update(source_system.name for source_system in source_systems)

    def create_pipeline_run(self, pipeline_name: str) -> UUID:
        pipeline_run_id = self._uuid()
        self.pipeline_runs[pipeline_run_id] = {
            "pipeline_name": pipeline_name,
            "status": "running",
        }
        return pipeline_run_id

    def checksum_was_loaded(self, source_system: str, checksum: str) -> bool:
        return (source_system, checksum) in self.loaded_checksums

    def create_source_file(self, source_file: SourceFileAudit) -> UUID:
        source_file_id = self._uuid()
        self.source_files[source_file_id] = (source_file, "discovered")
        return source_file_id

    def mark_source_file_loaded(self, source_file_id: UUID) -> None:
        audit, _ = self.source_files[source_file_id]
        self.source_files[source_file_id] = (audit, "loaded")
        self.loaded_checksums.add((audit.source_system, audit.sha256_checksum))

    def mark_source_file_failed(self, source_file_id: UUID) -> None:
        audit, _ = self.source_files[source_file_id]
        self.source_files[source_file_id] = (audit, "failed")

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
        self.pipeline_runs[pipeline_run_id].update(
            {
                "status": status,
                "discovered": discovered,
                "loaded": loaded,
                "failed": failed,
                "error_message": error_message,
            }
        )


class FakeObjectStore:
    def __init__(self, failing_filename: str | None = None) -> None:
        self.failing_filename = failing_filename
        self.uploads: list[tuple[str, str, Path]] = []

    def upload_file(self, bucket: str, object_path: str, local_path: Path) -> None:
        if local_path.name == self.failing_filename:
            raise RuntimeError("synthetic upload failure")
        self.uploads.append((bucket, object_path, local_path))

    def read_object(self, bucket: str, object_path: str) -> bytes:
        raise AssertionError("Raw ingestion must not read objects")


def _generated_input(tmp_path: Path, students: int = 5) -> Path:
    return generate_data(
        GeneratorOptions(
            seed=2026,
            students=students,
            output_directory=tmp_path,
        )
    ).output_path


def _service(
    metadata: FakeMetadataStore,
    object_store: FakeObjectStore,
) -> RawFileIngestionService:
    return RawFileIngestionService(
        metadata,
        object_store,
        MinioSettings(),
        now=lambda: datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc),
    )


def test_sha256_file_matches_known_digest(tmp_path: Path) -> None:
    source_file = tmp_path / "source.bin"
    source_file.write_bytes(b"synthetic source data")

    assert sha256_file(source_file) == hashlib.sha256(b"synthetic source data").hexdigest()


def test_discovery_uses_contract_patterns_and_manifest(tmp_path: Path) -> None:
    input_dir = _generated_input(tmp_path)
    configuration = load_configuration()

    context = load_generation_context(input_dir)
    discovered = discover_source_files(input_dir, configuration)

    assert context.school_year == "2025-2026"
    assert context.synthetic_data is True
    assert [source_file.filename for source_file in discovered] == [
        "assessments.xlsx",
        "attendance_events.jsonl",
        "enrollments.csv",
        "students.csv",
    ]
    assert "generation_manifest.json" not in {source_file.filename for source_file in discovered}


def test_discovery_rejects_manifest_without_synthetic_label(tmp_path: Path) -> None:
    input_dir = _generated_input(tmp_path)
    manifest_path = input_dir / "generation_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["synthetic_data"] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DiscoveryError, match="synthetic_data=true"):
        load_generation_context(input_dir)


def test_second_ingestion_skips_duplicates_without_new_file_records(tmp_path: Path) -> None:
    input_dir = _generated_input(tmp_path)
    configuration = load_configuration()
    metadata = FakeMetadataStore()
    object_store = FakeObjectStore()
    service = _service(metadata, object_store)

    first = service.ingest(input_dir, configuration)
    second = service.ingest(input_dir, configuration)

    assert first.uploaded == 4
    assert first.skipped == 0
    assert second.uploaded == 0
    assert second.skipped == 4
    assert len(object_store.uploads) == 4
    assert len(metadata.source_files) == 4
    assert all(status == "loaded" for _, status in metadata.source_files.values())
    assert all(
        object_path.startswith(
            (
                "simulated_assessments/2025-2026/2026-07-29/",
                "simulated_attendance/2025-2026/2026-07-29/",
                "simulated_sis/2025-2026/2026-07-29/",
            )
        )
        for _, object_path, _ in object_store.uploads
    )


def test_changed_file_with_same_name_is_uploaded_as_new_version(tmp_path: Path) -> None:
    input_dir = _generated_input(tmp_path)
    configuration = load_configuration()
    metadata = FakeMetadataStore()
    object_store = FakeObjectStore()
    service = _service(metadata, object_store)
    service.ingest(input_dir, configuration)
    students_path = input_dir / "students.csv"
    students_path.write_text(
        f"{students_path.read_text(encoding='utf-8')}SYN-NEW-VERSION\n",
        encoding="utf-8",
    )

    result = service.ingest(input_dir, configuration)

    assert result.uploaded == 1
    assert result.skipped == 3
    assert len(metadata.source_files) == 5
    student_versions = [
        audit
        for audit, status in metadata.source_files.values()
        if audit.original_filename == "students.csv" and status == "loaded"
    ]
    assert len(student_versions) == 2
    assert student_versions[0].sha256_checksum != student_versions[1].sha256_checksum
    assert input_dir.joinpath("students.csv").name == student_versions[1].original_filename


def test_failed_upload_is_recorded_without_losing_successes(tmp_path: Path) -> None:
    input_dir = _generated_input(tmp_path)
    configuration = load_configuration()
    metadata = FakeMetadataStore()
    object_store = FakeObjectStore(failing_filename="attendance_events.jsonl")

    result = _service(metadata, object_store).ingest(input_dir, configuration)

    statuses = [status for _, status in metadata.source_files.values()]
    assert result.status == "failed"
    assert result.uploaded == 3
    assert result.failed == 1
    assert statuses.count("loaded") == 3
    assert statuses.count("failed") == 1

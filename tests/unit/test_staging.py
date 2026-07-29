from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from uuid import UUID

import pytest

from k12hub.config import MinioSettings
from k12hub.contracts import ConfigurationBundle, SourceContract, load_configuration
from k12hub.generator import GeneratorOptions, generate_data
from k12hub.staging import (
    FileStructureError,
    ParsedFile,
    RowCountReconciliation,
    SourceFileReference,
    StagingLoaderService,
    parse_object,
)


def _generated_input(tmp_path: Path, students: int = 5) -> Path:
    return generate_data(
        GeneratorOptions(seed=7007, students=students, output_directory=tmp_path)
    ).output_path


def test_parses_every_supported_format(tmp_path: Path) -> None:
    input_dir = _generated_input(tmp_path)
    configuration = load_configuration()
    manifest = json.loads((input_dir / "generation_manifest.json").read_text(encoding="utf-8"))
    expected = {
        "sis_students": "students.csv",
        "sis_enrollment": "enrollments.csv",
        "attendance_events": "attendance_events.jsonl",
        "assessments": "assessments.xlsx",
    }

    for contract_name, filename in expected.items():
        expected_count = manifest["record_counts"][filename]
        parsed = parse_object(
            (input_dir / filename).read_bytes(),
            configuration.contracts[contract_name],
        )
        assert parsed.discovered == expected_count
        assert parsed.parsed == expected_count
        assert parsed.rejected == 0
        assert parsed.parsed_rows[0].raw_payload


def test_normalizes_column_names_predictably(tmp_path: Path) -> None:
    input_dir = _generated_input(tmp_path, students=1)
    content = (input_dir / "students.csv").read_text(encoding="utf-8")
    content = content.replace("student_id", " Student ID ", 1)

    parsed = parse_object(content.encode(), load_configuration().contracts["sis_students"])

    assert parsed.parsed == 1
    assert parsed.parsed_rows[0].business_values["student_id"].startswith("SYN-")
    assert " Student ID " in parsed.parsed_rows[0].raw_payload


def test_gate_reconciles_100_rows_with_three_malformed(tmp_path: Path) -> None:
    input_dir = _generated_input(tmp_path, students=100)
    source = io.StringIO((input_dir / "students.csv").read_text(encoding="utf-8"))
    rows = list(csv.reader(source))
    birth_date_index = rows[0].index("birth_date")
    for row in rows[1:4]:
        row[birth_date_index] = "not-a-date"
    output = io.StringIO()
    csv.writer(output, lineterminator="\n").writerows(rows)

    parsed = parse_object(
        output.getvalue().encode(),
        load_configuration().contracts["sis_students"],
    )

    assert parsed.discovered == 100
    assert parsed.parsed == 97
    assert parsed.rejected == 3
    assert parsed.parsed + parsed.rejected == parsed.discovered


def test_missing_required_columns_fails_structure_validation() -> None:
    content = b"first_name,last_name\nSynthetic,Student\n"

    with pytest.raises(FileStructureError, match="Missing required columns"):
        parse_object(content, load_configuration().contracts["sis_students"])


class FakeObjectStore:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.reads: list[tuple[str, str]] = []

    def upload_file(self, bucket: str, object_path: str, local_path: Path) -> None:
        raise AssertionError("Staging must not upload source objects")

    def read_object(self, bucket: str, object_path: str) -> bytes:
        self.reads.append((bucket, object_path))
        return self.content


class FakeStagingStore:
    def __init__(self, source_file: SourceFileReference) -> None:
        self.source_file = source_file
        self.parsed_file: ParsedFile | None = None

    def list_loaded_source_files(self, pipeline_run_id: UUID) -> list[SourceFileReference]:
        assert pipeline_run_id == self.source_file.pipeline_run_id
        return [self.source_file]

    def load_file(
        self,
        source_file: SourceFileReference,
        contract: SourceContract,
        parsed_file: ParsedFile,
    ) -> RowCountReconciliation:
        self.parsed_file = parsed_file
        return RowCountReconciliation(
            source_file_id=source_file.source_file_id,
            discovered=parsed_file.discovered,
            parsed=parsed_file.parsed,
            loaded=parsed_file.parsed,
            rejected=parsed_file.rejected,
            status="matched",
        )


def test_staging_service_reads_the_minio_object(
    tmp_path: Path,
) -> None:
    input_dir = _generated_input(tmp_path, students=1)
    pipeline_run_id = UUID(int=1)
    source_file = SourceFileReference(
        pipeline_run_id=pipeline_run_id,
        source_file_id=UUID(int=2),
        source_system="simulated_sis",
        original_filename="students.csv",
        object_path="raw/students.csv",
    )
    metadata = FakeStagingStore(source_file)
    object_store = FakeObjectStore((input_dir / "students.csv").read_bytes())
    configuration: ConfigurationBundle = load_configuration()

    result = StagingLoaderService(
        metadata,
        object_store,
        MinioSettings(),
    ).load(pipeline_run_id, configuration)

    assert object_store.reads == [("k12-raw", "raw/students.csv")]
    assert metadata.parsed_file is not None
    assert result.loaded == 1

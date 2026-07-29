from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest

from k12hub.contracts import ConfigurationBundle, load_configuration
from k12hub.generator import ERROR_TYPES, GeneratorOptions, generate_data
from k12hub.quality import (
    DataQualityRuleEngine,
    DatasetRow,
    QualityContext,
    SourceFileProfile,
)
from k12hub.staging import parse_object

ERROR_RULE_MAP = {
    "duplicate_student": {"STU-002"},
    "missing_student_identifier": {"STU-001"},
    "unknown_school_code": {"STU-003"},
    "invalid_grade": {"ENR-002"},
    "overlapping_enrollment": {"ENR-003"},
    "attendance_for_unknown_student": {"ATT-001", "ATT-003"},
    "duplicate_daily_attendance": {"ATT-005"},
    "attendance_outside_enrollment_period": {"ATT-003"},
    "invalid_attendance_status": {"ATT-004"},
    "attended_minutes_greater_than_possible": {"ATT-007"},
    "invalid_assessment_score": {"ASM-002"},
    "schema_drift_field": {"PIPE-003"},
}
SOURCE_FILES = (
    ("sis_students", "students.csv", "simulated_sis"),
    ("sis_enrollment", "enrollments.csv", "simulated_sis"),
    ("attendance_events", "attendance_events.jsonl", "simulated_attendance"),
    ("assessments", "assessments.xlsx", "simulated_assessments"),
)


def _context(
    input_dir: Path,
    configuration: ConfigurationBundle,
) -> QualityContext:
    pipeline_run_id = UUID(int=800)
    rows_by_dataset: dict[str, tuple[DatasetRow, ...]] = {}
    source_files: list[SourceFileProfile] = []
    for index, (contract_name, filename, source_system) in enumerate(SOURCE_FILES, start=1):
        contract = configuration.contracts[contract_name]
        source_file_id = UUID(int=index)
        parsed = parse_object((input_dir / filename).read_bytes(), contract)
        assert parsed.rejected == 0
        rows_by_dataset[contract.destination_staging_table] = tuple(
            DatasetRow(
                dataset=contract.destination_staging_table,
                pipeline_run_id=pipeline_run_id,
                source_file_id=source_file_id,
                source_system=source_system,
                source_row_number=row.source_row_number,
                source_schema_version=contract.schema_version,
                raw_payload=row.raw_payload,
                values=row.business_values,
            )
            for row in parsed.parsed_rows
        )
        source_files.append(
            SourceFileProfile(
                source_file_id=source_file_id,
                source_system=source_system,
                original_filename=filename,
                row_count=parsed.discovered,
                previous_row_count=None,
            )
        )
    return QualityContext(
        pipeline_run_id=pipeline_run_id,
        rows_by_dataset=rows_by_dataset,
        source_files=tuple(source_files),
        contracts_by_dataset={
            contract.destination_staging_table: contract
            for contract in configuration.contracts.values()
        },
    )


def _failed_rule_ids(
    input_dir: Path,
    configuration: ConfigurationBundle,
) -> set[str]:
    evaluations = DataQualityRuleEngine().evaluate(
        _context(input_dir, configuration),
        configuration.data_quality_rules.rules,
    )
    return {evaluation.rule.rule_id for evaluation in evaluations if evaluation.failure_count}


def test_clean_generated_dataset_passes_all_enabled_rules(tmp_path: Path) -> None:
    configuration = load_configuration()
    generated = generate_data(GeneratorOptions(seed=8000, students=8, output_directory=tmp_path))

    assert _failed_rule_ids(generated.output_path, configuration) == set()


@pytest.mark.parametrize("error_type", ERROR_TYPES)
def test_each_injected_error_maps_to_expected_rule_only(
    tmp_path: Path,
    error_type: str,
) -> None:
    configuration = load_configuration()
    generated = generate_data(
        GeneratorOptions(
            seed=8100 + ERROR_TYPES.index(error_type),
            students=8,
            error_rate=0.125,
            enabled_error_types=(error_type,),
            output_directory=tmp_path,
        )
    )

    assert generated.manifest["injected_errors"][error_type] == 1
    assert _failed_rule_ids(generated.output_path, configuration) == ERROR_RULE_MAP[error_type]


def test_disabled_rule_is_not_evaluated(tmp_path: Path) -> None:
    configuration = load_configuration()
    generated = generate_data(
        GeneratorOptions(
            seed=8200,
            students=8,
            error_rate=0.125,
            enabled_error_types=("missing_student_identifier",),
            output_directory=tmp_path,
        )
    )
    rules = [
        rule.model_copy(update={"enabled": False}) if rule.rule_id == "STU-001" else rule
        for rule in configuration.data_quality_rules.rules
    ]

    evaluations = DataQualityRuleEngine().evaluate(
        _context(generated.output_path, configuration),
        rules,
    )

    assert "STU-001" not in {evaluation.rule.rule_id for evaluation in evaluations}
    assert all(evaluation.failure_count == 0 for evaluation in evaluations)


def test_row_count_threshold_failure_is_nonblocking(tmp_path: Path) -> None:
    configuration = load_configuration()
    generated = generate_data(GeneratorOptions(seed=8300, students=8, output_directory=tmp_path))
    context = _context(generated.output_path, configuration)
    changed_file = context.source_files[0]
    context = QualityContext(
        pipeline_run_id=context.pipeline_run_id,
        rows_by_dataset=context.rows_by_dataset,
        source_files=(
            SourceFileProfile(
                source_file_id=changed_file.source_file_id,
                source_system=changed_file.source_system,
                original_filename=changed_file.original_filename,
                row_count=changed_file.row_count,
                previous_row_count=1,
            ),
            *context.source_files[1:],
        ),
        contracts_by_dataset=context.contracts_by_dataset,
    )
    pipe_rule = next(
        rule for rule in configuration.data_quality_rules.rules if rule.rule_id == "PIPE-001"
    )

    evaluation = DataQualityRuleEngine().evaluate(context, [pipe_rule])[0]

    assert evaluation.failure_count == 1
    assert evaluation.rule.blocking is False


def test_remaining_rule_failure_paths_are_config_driven(tmp_path: Path) -> None:
    configuration = load_configuration()
    generated = generate_data(GeneratorOptions(seed=8400, students=8, output_directory=tmp_path))
    context = _context(generated.output_path, configuration)
    rules = {rule.rule_id: rule for rule in configuration.data_quality_rules.rules}

    enrollment_rows = context.rows_by_dataset["staging.sis_enrollment"]
    invalid_enrollment = replace(
        enrollment_rows[0],
        values={
            **enrollment_rows[0].values,
            "entry_date": date(2026, 1, 2),
            "exit_date": date(2026, 1, 1),
        },
    )
    enrollment_context = replace(
        context,
        rows_by_dataset={
            **context.rows_by_dataset,
            "staging.sis_enrollment": (invalid_enrollment, *enrollment_rows[1:]),
        },
    )
    assert (
        DataQualityRuleEngine().evaluate(enrollment_context, [rules["ENR-001"]])[0].failure_count
        == 1
    )

    attendance_rows = context.rows_by_dataset["staging.attendance_event"]
    invalid_attendance = replace(
        attendance_rows[0],
        values={**attendance_rows[0].values, "school_id": "UNKNOWN"},
    )
    attendance_context = replace(
        context,
        rows_by_dataset={
            **context.rows_by_dataset,
            "staging.attendance_event": (invalid_attendance, *attendance_rows[1:]),
        },
    )
    assert (
        DataQualityRuleEngine().evaluate(attendance_context, [rules["ATT-002"]])[0].failure_count
        == 1
    )

    invalid_minutes_rule = rules["ATT-006"].model_copy(
        update={
            "parameters": {
                "parameter_name": "possible_minutes",
                "possible_minutes": 0,
            }
        }
    )
    assert DataQualityRuleEngine().evaluate(context, [invalid_minutes_rule])[
        0
    ].failure_count == len(attendance_rows)

    assessment_rows = context.rows_by_dataset["staging.assessment_event"]
    invalid_assessment = replace(
        assessment_rows[0],
        values={**assessment_rows[0].values, "student_id": "UNKNOWN"},
    )
    assessment_context = replace(
        context,
        rows_by_dataset={
            **context.rows_by_dataset,
            "staging.assessment_event": (invalid_assessment, *assessment_rows[1:]),
        },
    )
    assert (
        DataQualityRuleEngine().evaluate(assessment_context, [rules["ASM-001"]])[0].failure_count
        == 1
    )

    missing_file_context = replace(
        context,
        source_files=tuple(
            source_file
            for source_file in context.source_files
            if source_file.original_filename != "assessments.xlsx"
        ),
    )
    assert (
        DataQualityRuleEngine().evaluate(missing_file_context, [rules["PIPE-002"]])[0].failure_count
        == 1
    )

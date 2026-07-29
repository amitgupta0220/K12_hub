from pathlib import Path

import pytest

from k12hub.cli import main
from k12hub.contracts import (
    ConfigurationFileError,
    FileFormat,
    SensitiveClassification,
    load_configuration,
    load_source_contract,
)

CONFIG_DIR = Path("config")
STUDENT_CONTRACT = CONFIG_DIR / "contracts" / "sis_students.yml"


def test_complete_configuration_is_valid() -> None:
    configuration = load_configuration(CONFIG_DIR)

    assert set(configuration.contracts) == {
        "sis_students",
        "sis_enrollment",
        "attendance_events",
        "assessments",
    }
    assert configuration.contracts["attendance_events"].file_format is FileFormat.JSON_LINES
    assert configuration.contracts["assessments"].file_format is FileFormat.XLSX
    assert configuration.privacy.small_group_threshold == 10
    assert all(
        set(metric.model_fields_set) == {"name", "description"}
        for metric in configuration.metrics.metrics
    )
    assert {rule.rule_id for rule in configuration.data_quality_rules.rules} == {
        "STU-001",
        "STU-002",
        "STU-003",
        "ENR-001",
        "ENR-002",
        "ENR-003",
        "ATT-001",
        "ATT-002",
        "ATT-003",
        "ATT-004",
        "ATT-005",
        "ATT-006",
        "ATT-007",
        "ASM-001",
        "ASM-002",
        "PIPE-001",
        "PIPE-002",
        "PIPE-003",
    }
    assert all(
        rule.name and rule.remediation_guidance for rule in configuration.data_quality_rules.rules
    )


def test_contract_defines_required_privacy_metadata() -> None:
    contract = load_source_contract(STUDENT_CONTRACT)
    fields = {field.name: field for field in contract.expected_fields}

    assert contract.expected_grain == "one row per student"
    assert contract.natural_key == ["student_id"]
    assert contract.destination_staging_table == "staging.sis_student"
    assert (
        fields["student_id"].sensitive_classification is SensitiveClassification.DIRECT_IDENTIFIER
    )


def test_invalid_contract_type_is_rejected(tmp_path: Path) -> None:
    invalid_contract = tmp_path / "sis_students.yml"
    text = STUDENT_CONTRACT.read_text(encoding="utf-8")
    invalid_contract.write_text(
        text.replace('schema_version: "1.0.0"', "schema_version: 1"),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationFileError, match="schema_version"):
        load_source_contract(invalid_contract)


def test_unknown_contract_field_is_rejected(tmp_path: Path) -> None:
    invalid_contract = tmp_path / "sis_students.yml"
    invalid_contract.write_text(
        f"{STUDENT_CONTRACT.read_text(encoding='utf-8')}\nunknown_option: true\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationFileError, match="unknown_option"):
        load_source_contract(invalid_contract)


def test_malformed_yaml_has_useful_error(tmp_path: Path) -> None:
    invalid_contract = tmp_path / "invalid.yml"
    invalid_contract.write_text("expected_fields: [\n", encoding="utf-8")

    with pytest.raises(ConfigurationFileError, match="invalid YAML"):
        load_source_contract(invalid_contract)


def test_unknown_required_field_is_rejected(tmp_path: Path) -> None:
    invalid_contract = tmp_path / "sis_students.yml"
    text = STUDENT_CONTRACT.read_text(encoding="utf-8")
    invalid_contract.write_text(
        text.replace("  - active\nnatural_key:", "  - active\n  - missing_field\nnatural_key:"),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationFileError, match="required_fields contains unknown fields"):
        load_source_contract(invalid_contract)


def test_validate_config_cli_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["validate-config", "--config-dir", str(CONFIG_DIR)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Configuration valid: 4 contracts" in captured.out
    assert captured.err == ""

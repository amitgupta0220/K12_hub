"""Tests for dbt expected-metric variable generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.dbt_expected_metrics import REQUIRED_METRICS, load_dbt_vars


def _payload() -> dict[str, object]:
    return {
        "instructional_days": 175,
        "metrics": {
            "assessment_event_count": 20,
            "assessment_proficiency_rate": 0.7,
            "attendance_rate": 0.95,
            "chronic_absence_rate": 0.1,
            "enrollment_count": 10,
            "student_count": 10,
        },
        "school_year": "2025-2026",
        "synthetic_data": True,
    }


def test_load_dbt_vars_accepts_aggregate_synthetic_metrics(tmp_path: Path) -> None:
    path = tmp_path / "expected_metrics.json"
    path.write_text(json.dumps(_payload()), encoding="utf-8")

    variables = load_dbt_vars(path)

    expected = variables["expected_metrics"]
    assert set(expected) == REQUIRED_METRICS | {"instructional_days", "school_year"}
    assert expected["student_count"] == 10


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("synthetic_data", False),
        ("instructional_days", -1),
        ("school_year", ""),
    ],
)
def test_load_dbt_vars_rejects_invalid_metadata(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    payload = _payload()
    payload[field] = value
    path = tmp_path / "expected_metrics.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError):
        load_dbt_vars(path)


def test_load_dbt_vars_rejects_missing_metric(tmp_path: Path) -> None:
    payload = _payload()
    metrics = payload["metrics"]
    assert isinstance(metrics, dict)
    metrics.pop("student_count")
    path = tmp_path / "expected_metrics.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="exactly"):
        load_dbt_vars(path)

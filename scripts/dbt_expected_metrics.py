"""Translate a synthetic expected_metrics.json file into dbt variables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_METRICS = {
    "assessment_event_count",
    "assessment_proficiency_rate",
    "attendance_rate",
    "chronic_absence_rate",
    "enrollment_count",
    "student_count",
}


def load_dbt_vars(path: Path) -> dict[str, Any]:
    """Load and validate aggregate-only synthetic expectations for dbt."""

    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Unable to read expected metrics from {path}: {error}") from error
    if not isinstance(payload, dict) or payload.get("synthetic_data") is not True:
        raise ValueError("Expected metrics must be labeled synthetic_data=true")
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict) or set(metrics) != REQUIRED_METRICS:
        raise ValueError(f"Expected metrics must contain exactly: {sorted(REQUIRED_METRICS)}")
    instructional_days = payload.get("instructional_days")
    school_year = payload.get("school_year")
    if not isinstance(instructional_days, int) or instructional_days < 0:
        raise ValueError("instructional_days must be a nonnegative integer")
    if not isinstance(school_year, str) or not school_year:
        raise ValueError("school_year must be a non-empty string")
    return {
        "expected_metrics": {
            **metrics,
            "instructional_days": instructional_days,
            "school_year": school_year,
        }
    }


def main() -> int:
    """Print compact JSON suitable for dbt's --vars argument."""

    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    arguments = parser.parse_args()
    try:
        variables = load_dbt_vars(arguments.path)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(variables, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Data-quality rules

## Purpose

The data-quality engine evaluates staged synthetic data through the declarative rules in
`config/data_quality_rules.yml`. Thresholds, accepted values, blocking behavior, severity, and
remediation guidance live in YAML rather than CLI or future dashboard code.

Run validation for a staged ingestion with:

```sh
python -m k12hub.cli validate-data --pipeline-run-id <id>
```

The command prints a rule-by-rule terminal summary. It exits successfully when there are no
blocking failures. Non-blocking failures are still displayed and persisted for dashboard use.

For a new clean local demo:

```sh
make validate-demo
```

## Configuration schema

Every rule declares:

| Field | Meaning |
| --- | --- |
| `rule_id` | Stable human-facing rule code such as `ATT-004` |
| `name` | Short display name |
| `description` | Human-readable condition |
| `dataset` | Allowlisted staging dataset or `pipeline` |
| `rule_type` | Reusable evaluator selected by the engine |
| `severity` | `info`, `warning`, `error`, or `critical` |
| `blocking` | Whether failures also enter quarantine |
| `parameters` | Rule-specific fields, accepted values, references, ranges, or thresholds |
| `remediation_guidance` | Corrective action stored with each failure |
| `enabled` | Whether the engine evaluates the rule |

Disabling a rule in YAML removes it from subsequent rule runs without changing code. Configuration
loading rejects unknown fields, duplicate rule IDs, unknown datasets, and unsupported rule types.

## Initial rule catalog

| Rule | Dataset | Behavior |
| --- | --- | --- |
| `STU-001` | Student | Student identifier is required |
| `STU-002` | Student | Student identifier is unique within the source file |
| `STU-003` | Student | School identifier matches the registered school namespace |
| `ENR-001` | Enrollment | Entry date does not occur after exit date |
| `ENR-002` | Enrollment | Grade uses the configured accepted values |
| `ENR-003` | Enrollment | Periods do not overlap for the same student |
| `ATT-001` | Attendance | Student exists in staged students |
| `ATT-002` | Attendance | School identifier matches the registered school namespace |
| `ATT-003` | Attendance | Date is inside a staged enrollment period |
| `ATT-004` | Attendance | Status uses the configured accepted values |
| `ATT-005` | Attendance | One row per student and instructional date |
| `ATT-006` | Attendance | Configured possible minutes are positive |
| `ATT-007` | Attendance | Attended minutes do not exceed configured possible minutes |
| `ASM-001` | Assessment | Student exists in staged students |
| `ASM-002` | Assessment | Score is inside the configured inclusive range |
| `PIPE-001` | Pipeline | Row-count change stays within the configured percentage threshold |
| `PIPE-002` | Pipeline | Every configured required file arrived |
| `PIPE-003` | Pipeline | Schema version is known and source fields are declared |

## Failure and aggregate persistence

Each invocation creates one `audit.data_quality_rule_run`. One
`audit.data_quality_rule_result` per enabled rule stores evaluated and failed counts for dashboards.
Every row or pipeline failure is recorded in `audit.data_quality_failure` with:

- pipeline and quality-run identifiers;
- rule code and internal rule identifier;
- source file and source row, using row zero for pipeline-level checks;
- severity and blocking status;
- failure message and remediation guidance;
- original raw payload or pipeline evidence.

Blocking failures are also copied into `quarantine.rejected_record`. Non-blocking failures remain
available in staging and are flagged only in the quality audit tables. Re-running validation
creates a new auditable quality run while the existing quarantine uniqueness key prevents duplicate
blocking copies for the same immutable source row and rule.

## Synthetic injection mapping

The generator regression gate enforces this mapping:

| Injection | Expected rule failures |
| --- | --- |
| `duplicate_student` | `STU-002` |
| `missing_student_identifier` | `STU-001` |
| `unknown_school_code` | `STU-003` |
| `invalid_grade` | `ENR-002` |
| `overlapping_enrollment` | `ENR-003` |
| `attendance_for_unknown_student` | `ATT-001`, `ATT-003` |
| `duplicate_daily_attendance` | `ATT-005` |
| `attendance_outside_enrollment_period` | `ATT-003` |
| `invalid_attendance_status` | `ATT-004` |
| `attended_minutes_greater_than_possible` | `ATT-007` |
| `invalid_assessment_score` | `ASM-002` |
| `schema_drift_field` | `PIPE-003` |

The unknown attendance student necessarily also lacks an enrollment, so `ATT-003` is a logically
required related failure. Tests reject every other unrelated rule failure.

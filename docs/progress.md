# Project Progress

## Current phase

Prompt 8 — configuration-driven data-quality validation.

## Completed work

- Inspected the initial workspace and local tool availability.
- Added permanent repository engineering instructions.
- Documented the fixed project scope, technology stack, data boundaries, and version 1 exclusions.
- Established an architecture decision log.
- Added a Python 3.9-compatible `src`-layout package.
- Added environment-based configuration with safe local and test defaults and explicit
  production-mode validation.
- Added structured JSON logging with an optional plain-text local format.
- Added pytest, coverage, Ruff, and strict mypy configuration.
- Added unit tests for configuration, imports, and logging setup.
- Added repository setup and quality commands, environment examples, ignore rules, and
  empty data-directory markers.
- Added Docker Compose services for PostgreSQL 16 and MinIO with named volumes and health checks.
- Added an idempotent one-time MinIO initializer for the `k12-raw`, `k12-standardized`, and
  `k12-quarantine` buckets.
- Added typed local PostgreSQL and MinIO configuration with safe, overridable defaults.
- Added service connectivity checks and marked integration tests.
- Added infrastructure lifecycle commands and an interactive warning before volume deletion.
- Documented local services, ports, buckets, and the infrastructure architecture.
- Added Alembic initialization and a transactional operational-schema migration.
- Created the `metadata`, `raw`, `staging`, `core`, `mart`, `audit`, and `quarantine` schemas.
- Added three metadata tables, four audit tables, and one quarantine table with UUID keys,
  constraints, timestamps, relationships, and audit lookup indexes.
- Kept `raw`, `staging`, `core`, and `mart` empty for future dbt-managed analytical models.
- Added SQLAlchemy database URL, engine, and transaction utilities.
- Added migration lifecycle commands and unit and integration coverage.
- Added registered simulated source systems and versioned contracts for SIS students, SIS
  enrollment, attendance events, and assessments.
- Defined declarative data-quality rules, privacy controls, and metric names and descriptions.
- Added strict typed models for YAML loading, per-file validation, and cross-file reference checks.
- Added `python -m k12hub.cli validate-config`.
- Added valid, malformed, unknown-field, invalid-reference, and invalid-type contract tests.
- Added a deterministic generator for one fictitious intermediate district, three local
  districts, 12 schools, and grade-appropriate student assignments.
- Added synthetic student, enrollment, attendance, and assessment output in the contracted CSV,
  JSON Lines, and XLSX formats.
- Added a generation manifest containing arguments, hierarchy metadata, baseline and emitted
  record counts, injected-error counts, and SHA-256 checksums.
- Added clean-baseline expected aggregate metrics for enrollment, attendance, chronic absence,
  assessment volume, and assessment proficiency.
- Added all 12 requested configurable error-injection modes and CLI controls for seed, size,
  school year, error rate, enabled error types, and output location.
- Added generator tests covering byte-level determinism, seed variation, clean relational
  consistency, every requested injected error, manifest integrity, metric calculations, and CLI
  operation.
- Aligned contract file patterns and district relationships with the generated file set.
- Added configuration-driven discovery of generated source files using registered, enabled source
  contracts.
- Added manifest validation for synthetic-data labeling and school-year routing.
- Added streaming SHA-256 calculation and source-system/checksum duplicate detection.
- Added idempotent raw-file ingestion that preserves unchanged source bytes in the MinIO
  `k12-raw` bucket.
- Added versioned raw object paths containing source system, school year, ingestion date, pipeline
  run identifier, and original filename.
- Added transactional PostgreSQL pipeline-run and source-file audit updates, including per-file
  failure recording without rolling back successful uploads from the same run.
- Added a checksum/status lookup index for duplicate detection.
- Added the `python -m k12hub.cli ingest` command and a reproducible `make ingest-demo` workflow.
- Added unit and integration coverage for discovery, checksums, duplicate skipping, changed-file
  versioning, upload failures, PostgreSQL audit metadata, and MinIO objects.
- Documented the raw-ingestion boundary, object layout, idempotency decision, and local usage.
- Added Alembic-managed `staging.sis_student`, `staging.sis_enrollment`,
  `staging.attendance_event`, and `staging.assessment_event` tables with typed business columns and
  common source-lineage metadata.
- Added MinIO object reads and contract-driven CSV, JSON Lines, and XLSX parsers.
- Added predictable lower-snake-case column normalization, required-column validation, typed field
  parsing, accepted-value checks, and original-row JSONB preservation.
- Added row-level parse quarantine with retry-safe uniqueness.
- Added batch staging inserts and atomic per-source-file transactions.
- Added discovered, parsed, loaded, and rejected counts to row-count reconciliation.
- Added source-file row locking and `(source_file_id, source_row_number)` idempotency so retries
  cannot create full or partial duplicate loads.
- Added `load-staging` and combined `run-ingestion` CLI commands; the combined command delegates to
  the existing raw-ingestion and staging services.
- Added unit and integration coverage for all formats, malformed records, missing columns,
  normalization, MinIO-only reads, idempotent retry, reconciliation, and transaction rollback.
- Documented staging usage, ownership, flow, atomicity, and retry behavior.
- Expanded the declarative quality-rule schema with names, datasets, blocking behavior,
  remediation guidance, enablement, and reusable evaluator types.
- Added 18 initial student, enrollment, attendance, assessment, and pipeline-level quality rules.
- Added a reusable Python rule engine with configuration-driven required, uniqueness, reference,
  date, accepted-value, overlap, range, volume, required-file, and schema-version evaluators.
- Added auditable quality-run, rule-result, and failure persistence with stable rule identifiers.
- Added blocking-failure quarantine while retaining non-blocking warnings in staging and audit
  history.
- Added `python -m k12hub.cli validate-data --pipeline-run-id <id>` with rule-by-rule terminal
  output and blocking-aware exit behavior.
- Added the reproducible `make validate-demo` workflow and documented the complete quality-rule
  catalog, persistence model, and synthetic error-injection mapping.
- Added unit and integration coverage for clean data, each injected error type, non-blocking
  volume warnings, persistence, quarantine behavior, and rerun safety.
- Changed Make dependency installation to use a `pyproject.toml`-sensitive environment stamp so
  repeated quality commands do not require unnecessary package-index access.

## Validation results

- Passed the Prompt 0 document gate on 2026-07-29 using Python 3.9.6.
- Confirmed that `AGENTS.md`, `docs/project_scope.md`, `docs/progress.md`, and `docs/decisions.md` exist.
- Confirmed that each document contains its required sections and that the decision log contains an ADR entry.
- Two earlier attempts could not run because neither `rg` nor `grep` is installed in the environment; these were tooling failures, not failed content assertions.
- `make verify` passed on 2026-07-29.
- Ruff formatting check: passed for 5 files.
- Ruff lint: passed.
- mypy: passed with no issues in 5 source files.
- pytest: 12 tests passed.
- Coverage: 94% total.
- Earlier Prompt 1 verification attempts stopped during restricted dependency installation and
  on formatting/lint findings; dependency access and all reported findings were corrected before
  the successful full gate.
- `docker compose config` passed on 2026-07-29.
- `make infra-up` passed with healthy PostgreSQL and MinIO services and successful bucket
  initialization.
- `make infra-check` passed the service probes and 2 marked integration tests.
- `make verify` passed after all Prompt 2 changes.
- Ruff formatting and lint checks passed for 9 files.
- mypy passed with no issues in 9 source files.
- pytest passed 19 unit tests with 2 integration tests deselected.
- Unit-test coverage was 93%.
- `make db-upgrade` passed and applied Alembic revision `20260729_0001`.
- `make migration-test` passed 2 migration integration tests.
- A uniquely named clean database successfully ran the full migration twice without
  duplicate-object failures; all required schemas, tables, columns, and indexes were verified.
- `make verify` passed after all Prompt 3 changes.
- Ruff formatting and lint checks passed for 14 files.
- mypy passed with no issues in 12 source files.
- pytest passed 23 unit tests with 4 integration tests deselected.
- Unit-test coverage remained 93%.
- `make verify` passed after all Prompt 4 changes.
- Ruff formatting and lint checks passed for 17 files.
- mypy passed with no issues in 15 source files.
- pytest passed 30 unit tests with 4 integration tests deselected.
- Unit-test coverage was 87%.
- `.venv/bin/python -m k12hub.cli validate-config` passed with 4 contracts, 6 data-quality rules,
  and 6 metric definitions.
- The invalid-type gate changed a temporary contract fixture from a string schema version to an
  integer; the targeted validation test passed by rejecting the invalid type, and the valid
  contract remained restored.
- `make verify` passed after all Prompt 5 changes.
- Ruff formatting and lint checks passed for 19 files.
- mypy passed with no issues in 17 source files.
- pytest passed 37 unit tests with 4 integration tests deselected.
- Unit-test coverage was 92%.
- `.venv/bin/python -m k12hub.cli validate-config` passed with 4 contracts, 6 data-quality rules,
  and 6 metric definitions after contract alignment.
- A small ignored fixture was generated with seed 2026 and 25 students at
  `data/generated/fixture/run-f57b686f98cfdb28`.
- Two independent 25-student runs with the same arguments produced identical directory contents,
  run identifiers, manifests, and SHA-256 checksums for all five checksummed data/metric files.
- Two independent runs of the requested 1,500-student command produced identical directory
  contents and checksums: 1,500 students, 1,500 enrollments, 266,760 attendance events, and 3,000
  assessment events.
- The full-size gate exposed variable XLSX modification metadata that two fast small runs had
  masked. The writer now normalizes both archive and workbook metadata, a regression assertion
  verifies the fixed timestamps, and the full-size determinism gate passes.
- `make verify` passed after all Prompt 6 changes.
- Ruff formatting check passed for 26 files, and Ruff lint passed with no findings.
- mypy passed with no issues in 23 source files.
- pytest passed 44 unit tests with 5 integration tests deselected; unit-test coverage was 87%.
- PostgreSQL and MinIO were healthy during Prompt 6 integration validation.
- Alembic revision `20260729_0002` applied successfully.
- The Prompt 6 MinIO/PostgreSQL ingestion test passed, confirming that a second ingestion skips all
  four exact duplicates without creating additional source-file audit rows.
- The complete integration suite passed all 5 tests.
- Alembic revision `20260729_0003` applied successfully.
- `make verify` passed after all Prompt 7 implementation and test changes.
- Ruff formatting and lint checks passed for 30 files.
- mypy passed with no issues in 26 source files.
- pytest passed 49 unit tests with 8 integration tests deselected; total unit-test coverage was
  81%.
- The complete integration suite passed all 8 tests.
- The 100-row malformed-record gate passed with 100 discovered, 97 parsed, 97 loaded, and 3
  quarantined rows.
- Idempotent retry preserved exactly one staging row per source file and source row number and one
  reconciliation per source file and stage.
- A forced failure after staging and quarantine inserts rolled back all row, reconciliation, and
  source-file count changes.
- The full 1,500-student demo loaded from MinIO into staging with manifest-matching counts: 1,500
  students, 1,500 enrollments, 266,981 attendance events, and 3,000 assessment events.
- All four full-demo reconciliations were matched: 272,981 discovered, parsed, and loaded rows with
  zero rejected rows.
- The first Prompt 7 migration attempt exposed schema-wide PostgreSQL index-name collisions; table
  names were added to retry-key constraint names before the successful migration gate.
- The first full-demo invocation used an incorrect generated run-directory suffix and produced an
  audited failure with no loaded files; rerunning with the exact generated path passed.
- `make validate-demo` completed successfully for a 25-student synthetic run: 4 raw files uploaded,
  4,457 rows discovered, parsed, and loaded, and zero staging rejections.
- The demo evaluated all 18 enabled quality rules with zero blocking failures and overall status
  `passed`.
- `PIPE-001` correctly recorded four non-blocking row-count-change warnings because the persistent
  local database contained a materially smaller prior run under the same pipeline name.
- The first Prompt 8 `make verify` attempt stopped on Ruff formatting findings in
  `tests/unit/test_quality.py`; the file was formatted before rerunning the complete gate.
- `make verify` passed after the formatting correction.
- Ruff formatting passed for 34 files and Ruff lint passed with no findings.
- mypy passed with no issues in 29 source files.
- pytest passed 65 unit tests with 11 integration tests deselected; unit-test coverage was 80%.
- The complete integration suite passed 11 tests against local PostgreSQL and MinIO; integration
  coverage was 85%.

## Known issues

- The system Python 3.9 runtime uses LibreSSL 2.8.3, so urllib3 emits a compatibility warning.
  Local MinIO uses HTTP and all connectivity checks pass; a newer Python/OpenSSL runtime will
  remove the warning.

## Next recommended phase

Provide the next numbered prompt. No generated student-level data is tracked in version control.
No Airflow, dbt models, Streamlit, conformed student warehouse tables, conformed attendance
warehouse tables, or analytical models have been started.

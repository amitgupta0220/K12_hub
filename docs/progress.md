# Project Progress

## Current phase

Prompt 5 — deterministic synthetic-data generator.

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

## Known issues

- The system Python 3.9 runtime uses LibreSSL 2.8.3, so urllib3 emits a compatibility warning.
  Local MinIO uses HTTP and all connectivity checks pass; a newer Python/OpenSSL runtime will
  remove the warning.

## Next recommended phase

Provide the next numbered project prompt. No generated student-level data is tracked in version
control. No Airflow, dbt models, Streamlit, ingestion logic, student warehouse tables, attendance
warehouse tables, or analytical models have been started.

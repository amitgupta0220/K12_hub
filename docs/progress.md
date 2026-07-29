# Project Progress

## Current phase

Prompt 2 — PostgreSQL and MinIO local infrastructure.

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

## Known issues

- The system Python 3.9 runtime uses LibreSSL 2.8.3, so urllib3 emits a compatibility warning.
  Local MinIO uses HTTP and all connectivity checks pass; a newer Python/OpenSSL runtime will
  remove the warning.

## Next recommended phase

Provide the next numbered project prompt. No Airflow, dbt, Streamlit, ingestion logic, or
warehouse tables have been started.

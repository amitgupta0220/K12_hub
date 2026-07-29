# K-12 Data Reliability Hub

## Project purpose

K-12 Data Reliability Hub is an OAISD-inspired, local-first portfolio project demonstrating reliable, privacy-aware K-12 data infrastructure.

## Current development status

The repository currently provides the typed Python package foundation, local PostgreSQL and MinIO
infrastructure, Alembic-managed operational metadata schemas, environment-based configuration,
strict configuration-driven source contracts, deterministic synthetic-data generation, structured
logging, idempotent raw-file ingestion into MinIO with PostgreSQL audit metadata, connectivity
checks, contract-driven CSV/JSON Lines/XLSX parsing, transactional staging loads, row quarantine
and reconciliation, a configuration-driven data-quality rule engine with dashboard-ready audit
results, and quality tooling. Analytical models are not implemented yet.

## Basic setup

Python 3.9 or newer and GNU Make are required.

```sh
make install
cp .env.example .env
```

The project uses safe local defaults, so copying the example environment file is optional for local development.

Start the local services with `make infra-up` and verify them with `make infra-check`.
Initialize or update the operational database schemas with `make db-upgrade`.

Generate a fully synthetic dataset with:

```sh
python -m k12hub.cli generate-data --seed 2026 --students 1500 --school-year 2025-2026
```

Generated runs are written beneath `data/generated/`, are excluded from version control, and
include a manifest with record counts and SHA-256 checksums. Use `--help` to see error-injection
and output-directory options.

After starting the services and applying migrations, ingest one generated run with:

```sh
python -m k12hub.cli ingest --input-dir data/generated/<run-id> --source all
```

Ingestion reads the generated manifest for the school year, uploads only contract-matched source
files to `k12-raw`, and records pipeline and file audit metadata. Exact checksums already marked
loaded are skipped; changed content with the same filename is retained as a new raw version.

Load the raw objects for that pipeline run into staging with:

```sh
python -m k12hub.cli load-staging --pipeline-run-id <id>
```

For a new generated run, both steps can be invoked without duplicating service logic:

```sh
python -m k12hub.cli run-ingestion --input-dir data/generated/<run-id>
```

Staging always reads the immutable MinIO objects. It validates normalized columns against the
source contracts, preserves every original row in JSONB, loads valid rows into the four typed
staging tables, quarantines malformed rows, and writes discovered/parsed/loaded/rejected
reconciliation counts. Retrying `load-staging` with the same pipeline run is idempotent.

Validate the staged rows with the enabled YAML rules:

```sh
python -m k12hub.cli validate-data --pipeline-run-id <id>
```

Blocking failures are copied to quarantine. Non-blocking failures remain available and are flagged
in the audit tables. See `docs/data_quality_rules.md` for the rule catalog and generator mapping.

| Service | Purpose | Local port |
| --- | --- | --- |
| PostgreSQL | Warehouse and operational metadata database (`k12hub`) | `5432` |
| MinIO API | S3-compatible object storage | `9000` |
| MinIO console | Local object-storage administration | `9001` |

MinIO initializes the private `k12-raw`, `k12-standardized`, and `k12-quarantine` buckets. Ports and safe local-only credentials can be overridden in an uncommitted `.env` file.

## Available quality commands

```sh
make format
make lint
make typecheck
make test
make verify
make infra-up
make infra-check
make infra-logs
make infra-down
make infra-reset
make db-upgrade
make db-current
make db-downgrade
make migration-test
make ingest-demo
make validate-demo
python -m k12hub.cli validate-config
python -m k12hub.cli generate-data --help
python -m k12hub.cli ingest --help
python -m k12hub.cli load-staging --help
python -m k12hub.cli run-ingestion --help
python -m k12hub.cli validate-data --help
```

## Synthetic-data disclaimer

This project must never use real student information. Any student-level or operational examples are deterministic synthetic data and must be clearly labeled and kept separate from clearly sourced public aggregate datasets.

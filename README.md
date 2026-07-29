# K-12 Data Reliability Hub

## Project purpose

K-12 Data Reliability Hub is an OAISD-inspired, local-first portfolio project demonstrating reliable, privacy-aware K-12 data infrastructure.

## Current development status

The repository currently provides the typed Python package foundation, local PostgreSQL and MinIO
infrastructure, Alembic-managed operational metadata schemas, environment-based configuration,
strict configuration-driven source contracts, deterministic synthetic-data generation, structured
logging, connectivity checks, and quality tooling. Data pipelines and analytical models are not
implemented yet.

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
python -m k12hub.cli validate-config
python -m k12hub.cli generate-data --help
```

## Synthetic-data disclaimer

This project must never use real student information. Any student-level or operational examples are deterministic synthetic data and must be clearly labeled and kept separate from clearly sourced public aggregate datasets.

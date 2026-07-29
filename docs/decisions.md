# Architecture Decision Log

This file is an append-only log of significant architectural decisions. New decisions receive the next sequential identifier. If a decision changes, add a new entry that supersedes the earlier one rather than silently rewriting history.

## Entry format

Each entry contains:

- **Status:** Proposed, Accepted, Superseded, or Rejected
- **Date:** `YYYY-MM-DD`
- **Context:** The problem and relevant constraints
- **Decision:** The selected approach
- **Consequences:** Expected benefits, costs, risks, and follow-up work

---

## ADR-0001: Use the fixed local-first platform stack

- **Status:** Accepted
- **Date:** 2026-07-29

### Context

The project is a portfolio demonstration of a K-12 data reliability platform that must run locally and show ingestion, storage, warehousing, transformation, orchestration, validation, reporting, and guarded natural-language querying.

### Decision

Use Python, Docker Compose, MinIO, PostgreSQL, dbt Core, Apache Airflow, Streamlit, Plotly, pytest, Ruff, mypy, and GitHub Actions. Data validation will use a Python rule engine and dbt tests. Natural-language questions will produce a validated structured query plan, optionally assisted by an LLM provider.

### Consequences

The architecture is reproducible on a local machine and demonstrates the intended data-platform layers. It also creates operational complexity from coordinating several services, so future phases must keep component responsibilities clear and add integration checks incrementally.

---

## ADR-0002: Separate synthetic and public data and prohibit real student data

- **Status:** Accepted
- **Date:** 2026-07-29

### Context

K-12 records are privacy-sensitive. The project needs realistic demonstrations and stable tests without collecting or exposing real student information or depending on mutable live websites.

### Decision

Use only deterministic synthetic data and public aggregate datasets. Keep the two categories clearly labeled and separated across storage, ingestion, fixtures, metadata, and documentation. Do not commit generated raw data, student-level generated datasets, database volumes, secrets, or credentials.

### Consequences

The project can demonstrate data-quality and delivery patterns with a low privacy risk and reproducible tests. Public-source provenance and synthetic-data labeling become required design concerns in every future ingestion path.

---

## ADR-0003: Guard natural-language queries with structured plans

- **Status:** Accepted
- **Date:** 2026-07-29

### Context

The platform must support English-language questions while preventing arbitrary or unsafe SQL execution.

### Decision

Convert questions into a structured query plan that is validated against allowlisted datasets, dimensions, metrics, filters, and limits. Application SQL must be read-only and parameterized. Never execute LLM output directly as SQL.

### Consequences

Chat functionality is constrained to supported analytical questions and is easier to audit and test. Adding a new query capability requires an explicit schema and validation update rather than unconstrained SQL generation.

---

## ADR-0004: Use lightweight typed environment configuration and standard-library logging

- **Status:** Accepted
- **Date:** 2026-07-29

### Context

The Python foundation needs environment-based configuration, test support, clear failures for
missing production-style values, and structured logging without introducing infrastructure or
business logic.

### Decision

Use `python-dotenv` to load optional local environment files into a typed, validated settings
dataclass. Provide safe local and test data-directory defaults, but require an explicit data
directory in production mode. Use Python's standard logging configuration with a JSON formatter
and an optional plain-text formatter.

### Consequences

Configuration remains small, deterministic, and straightforward to test. Future settings must be
added through the same validation boundary. The project avoids a larger settings framework for
now, while retaining the option to adopt one if configuration complexity grows.

---

## ADR-0005: Run the initial persistence layer through Docker Compose

- **Status:** Accepted
- **Date:** 2026-07-29

### Context

The project needs reproducible local PostgreSQL and S3-compatible storage without introducing
cloud services or later platform components prematurely.

### Decision

Run PostgreSQL 16 and MinIO through Docker Compose with named volumes and health checks. Use safe
local-only default credentials that can be overridden in an uncommitted `.env` file. Initialize
three private, purpose-specific buckets through an idempotent one-time MinIO client service:
`k12-raw`, `k12-standardized`, and `k12-quarantine`.

Keep Docker-dependent tests marked as `integration`. Run them through `make infra-check`, while
the default unit-test and verification paths remain usable without Docker.

### Consequences

Developers get persistent, locally reproducible services and explicit object-storage boundaries.
Resetting infrastructure requires intentional volume deletion and loses local state. Later phases
may build on these services but must not collapse raw, standardized, and quarantined objects into
one bucket.

---

## ADR-0006: Separate operational migrations from analytical transformations

- **Status:** Accepted
- **Date:** 2026-07-29

### Context

PostgreSQL must hold durable operational metadata, audit history, and quarantined records while
also serving as the future analytical warehouse. Operational tables and analytical models have
different lifecycles and ownership.

### Decision

Use Alembic for the `metadata`, `audit`, and `quarantine` operational tables. Create the `raw`,
`staging`, `core`, and `mart` schema namespaces now but leave them empty for dbt to manage in a
later phase. Use PostgreSQL UUID primary keys, JSONB for structured contracts, rules, and rejected
payloads, and explicit indexes for common audit lookups.

Run each migration transactionally. Prove repeatability by applying the complete migration twice
to a uniquely named clean test database during the migration integration suite.

### Consequences

Operational state can evolve independently from warehouse transformations, and migration failures
roll back atomically. Empty analytical schemas make the future ownership boundary visible without
prematurely creating models. Integration tests require permission to create and remove a temporary
local PostgreSQL database.

---

## ADR-0007: Define source behavior through strict versioned YAML contracts

- **Status:** Accepted
- **Date:** 2026-07-29

### Context

Future ingestion and validation behavior must be reproducible across multiple simulated source
formats while keeping schema expectations, privacy classifications, quality rules, and metrics
reviewable before any file processing exists.

### Decision

Store source registrations, file contracts, data-quality rules, privacy controls, and metric
definitions as versioned YAML. Validate them with frozen Pydantic models that reject unknown keys
by default. Permit open-ended keys only inside the explicitly declared data-quality rule
`parameters` mapping.

Cross-validate source registrations, contract ownership, required fields, natural keys,
data-quality rule references, and privacy lists. Keep metrics limited to names and descriptions
until calculations are implemented in a later phase.

### Consequences

Invalid or inconsistent configuration fails before ingestion begins, and contract changes are
visible in version control. Adding new formats, field types, rule types, or configuration keys
requires an intentional model change and tests. The Python 3.9 runtime requires a small annotation
evaluation compatibility package for Pydantic's modern type syntax.

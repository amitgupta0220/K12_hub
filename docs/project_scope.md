# K-12 Data Reliability Hub: Project Scope

## Purpose

K-12 Data Reliability Hub is an OAISD-inspired, local-first portfolio project for demonstrating reliable and privacy-aware K-12 data infrastructure. It will:

- ingest data from multiple simulated education systems;
- load public Michigan and National Center for Education Statistics (NCES) aggregate datasets;
- validate records against configurable K-12 data-quality rules;
- quarantine invalid records;
- create trusted warehouse models and reporting marts;
- provide Streamlit dashboards;
- support English-language questions through a guarded, structured query-planning interface;
- demonstrate privacy-aware data delivery; and
- run locally with Docker Compose.

The project uses only clearly labeled synthetic data and public aggregate data. It must never contain real student information.

## Fixed technology stack

| Layer | Technology |
| --- | --- |
| Language | Python |
| Local environment | Docker Compose |
| Raw object storage | MinIO |
| Warehouse | PostgreSQL |
| Transformations | dbt Core |
| Orchestration | Apache Airflow |
| Data validation | Python rule engine and dbt tests |
| Dashboard | Streamlit and Plotly |
| Chat query planning | Structured query plan with optional LLM provider |
| Testing | pytest, dbt tests, and integration tests |
| Code quality | Ruff and mypy |
| Continuous integration | GitHub Actions |

## Data boundaries

- Synthetic student-level or operational data is generated deterministically for development and testing and is labeled `synthetic`.
- Public data is limited to public aggregate datasets, is labeled `public`, and retains source and provenance metadata.
- Synthetic and public data remain separate in storage locations, ingestion paths, fixtures, and documentation.
- Generated raw data, student-level generated datasets, database volumes, credentials, and `.env` files are local artifacts and are never committed.
- Live websites are not test dependencies; tests use deterministic fixtures.

## Version 1 exclusions

The following are explicitly out of scope:

- a complete Ed-Fi Operational Data Store implementation;
- production authentication;
- real student data;
- predictive student-risk scoring;
- cloud deployment;
- arbitrary LLM-generated SQL or direct execution of LLM output; and
- special education case management.

These exclusions may not be added implicitly during implementation. Any future scope change must be requested explicitly and recorded in the architecture decision log.

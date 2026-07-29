# Local Infrastructure Architecture

Prompt 2 establishes only the local persistence layer. PostgreSQL stores the future warehouse and
operational metadata, while MinIO provides separate S3-compatible buckets for raw, standardized,
and quarantined objects.

```mermaid
flowchart LR
    developer["Local developer"] --> compose["Docker Compose"]
    compose --> postgres["PostgreSQL<br/>localhost:5432"]
    compose --> minio["MinIO API<br/>localhost:9000"]
    compose --> console["MinIO console<br/>localhost:9001"]
    postgres --> postgres_volume[("postgres_data volume")]
    minio --> minio_volume[("minio_data volume")]
    initializer["One-time MinIO initializer"] --> minio
    minio --> raw["k12-raw"]
    minio --> standardized["k12-standardized"]
    minio --> quarantine["k12-quarantine"]
```

All credentials in `.env.example` are local-only defaults. Developers may override them in an
uncommitted `.env` file. Docker named volumes keep service state outside the repository.

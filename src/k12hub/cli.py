"""Command-line interface for repository operations."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

from k12hub.config import load_settings
from k12hub.contracts import ConfigurationFileError, load_configuration
from k12hub.database import create_database_engine
from k12hub.generator import ERROR_TYPES, GeneratorOptions, generate_data
from k12hub.ingestion import (
    IngestionError,
    PostgresIngestionMetadataStore,
    RawFileIngestionService,
)
from k12hub.logging_config import configure_logging
from k12hub.object_store import MinioObjectStorageClient
from k12hub.staging import (
    PostgresStagingMetadataStore,
    StagingLoadError,
    StagingLoaderService,
    StagingResult,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(prog="python -m k12hub.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser(
        "validate-config",
        help="validate all source-contract and policy configuration",
    )
    validate_parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("config"),
        help="configuration directory (default: config)",
    )
    generate_parser = subparsers.add_parser(
        "generate-data",
        help="generate a deterministic synthetic K-12 dataset",
    )
    generate_parser.add_argument("--seed", type=int, default=2026)
    generate_parser.add_argument("--students", type=int, default=1500)
    generate_parser.add_argument("--school-year", default="2025-2026")
    generate_parser.add_argument("--error-rate", type=float, default=0.0)
    generate_parser.add_argument(
        "--enabled-error-types",
        nargs="*",
        choices=ERROR_TYPES,
        default=[],
    )
    generate_parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("data/generated"),
    )
    ingest_parser = subparsers.add_parser(
        "ingest",
        help="ingest local contract-matched files into the MinIO raw zone",
    )
    ingest_parser.add_argument("--input-dir", type=Path, required=True)
    ingest_parser.add_argument("--source", default="all")
    ingest_parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("config"),
    )
    staging_parser = subparsers.add_parser(
        "load-staging",
        help="parse raw MinIO objects and load contract-driven staging tables",
    )
    staging_parser.add_argument("--pipeline-run-id", type=UUID, required=True)
    staging_parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("config"),
    )
    combined_parser = subparsers.add_parser(
        "run-ingestion",
        help="ingest local files to MinIO and load their rows into staging",
    )
    combined_parser.add_argument("--input-dir", type=Path, required=True)
    combined_parser.add_argument("--source", default="all")
    combined_parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("config"),
    )
    return parser


def _print_staging_result(result: StagingResult) -> None:
    print(
        "Staging load complete: "
        f"pipeline_run_id={result.pipeline_run_id} "
        f"files={result.files} "
        f"discovered={result.discovered} "
        f"parsed={result.parsed} "
        f"loaded={result.loaded} "
        f"rejected={result.rejected}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the requested CLI command."""

    args = build_parser().parse_args(argv)
    if args.command == "validate-config":
        try:
            configuration = load_configuration(args.config_dir)
        except ConfigurationFileError as error:
            print(f"Configuration invalid: {error}", file=sys.stderr)
            return 1
        print(
            "Configuration valid: "
            f"{len(configuration.contracts)} contracts, "
            f"{len(configuration.data_quality_rules.rules)} data-quality rules, "
            f"{len(configuration.metrics.metrics)} metrics"
        )
        return 0
    if args.command == "generate-data":
        try:
            options = GeneratorOptions(
                seed=args.seed,
                students=args.students,
                school_year=args.school_year,
                error_rate=args.error_rate,
                enabled_error_types=tuple(args.enabled_error_types),
                output_directory=args.output_directory,
            )
        except ValueError as error:
            print(f"Generator arguments invalid: {error}", file=sys.stderr)
            return 2
        generation_result = generate_data(options)
        print(f"Synthetic dataset generated: {generation_result.output_path}")
        return 0
    if args.command == "ingest":
        settings = load_settings()
        configure_logging(settings)
        try:
            configuration = load_configuration(args.config_dir)
        except ConfigurationFileError as error:
            print(f"Configuration invalid: {error}", file=sys.stderr)
            return 1

        engine = create_database_engine(settings.postgres)
        try:
            service = RawFileIngestionService(
                PostgresIngestionMetadataStore(engine),
                MinioObjectStorageClient(settings.minio),
                settings.minio,
            )
            ingestion_result = service.ingest(args.input_dir, configuration, args.source)
        except IngestionError as error:
            print(str(error), file=sys.stderr)
            return 1
        finally:
            engine.dispose()
        print(
            "Ingestion complete: "
            f"pipeline_run_id={ingestion_result.pipeline_run_id} "
            f"status={ingestion_result.status} "
            f"discovered={ingestion_result.discovered} "
            f"uploaded={ingestion_result.uploaded} "
            f"skipped={ingestion_result.skipped} "
            f"failed={ingestion_result.failed}"
        )
        return 1 if ingestion_result.failed else 0
    if args.command in {"load-staging", "run-ingestion"}:
        settings = load_settings()
        configure_logging(settings)
        try:
            configuration = load_configuration(args.config_dir)
        except ConfigurationFileError as error:
            print(f"Configuration invalid: {error}", file=sys.stderr)
            return 1

        engine = create_database_engine(settings.postgres)
        object_store = MinioObjectStorageClient(settings.minio)
        try:
            if args.command == "run-ingestion":
                ingestion_result = RawFileIngestionService(
                    PostgresIngestionMetadataStore(engine),
                    object_store,
                    settings.minio,
                ).ingest(args.input_dir, configuration, args.source)
                if ingestion_result.failed:
                    print(
                        f"Raw ingestion failed: pipeline_run_id={ingestion_result.pipeline_run_id}",
                        file=sys.stderr,
                    )
                    return 1
                pipeline_run_id = ingestion_result.pipeline_run_id
            else:
                pipeline_run_id = args.pipeline_run_id

            staging_result = StagingLoaderService(
                PostgresStagingMetadataStore(engine),
                object_store,
                settings.minio,
            ).load(pipeline_run_id, configuration)
        except (IngestionError, StagingLoadError) as error:
            print(str(error), file=sys.stderr)
            return 1
        finally:
            engine.dispose()
        _print_staging_result(staging_result)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

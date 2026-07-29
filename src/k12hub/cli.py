"""Command-line interface for repository operations."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from k12hub.contracts import ConfigurationFileError, load_configuration
from k12hub.generator import ERROR_TYPES, GeneratorOptions, generate_data


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
    return parser


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
        result = generate_data(options)
        print(f"Synthetic dataset generated: {result.output_path}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

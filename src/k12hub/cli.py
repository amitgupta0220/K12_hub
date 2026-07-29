"""Command-line interface for repository operations."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from k12hub.contracts import ConfigurationFileError, load_configuration


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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

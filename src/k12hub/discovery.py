"""Configuration-driven local source-file discovery."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from k12hub.contracts import ConfigurationBundle, SourceContract


class DiscoveryError(ValueError):
    """Raised when an input directory or generated manifest is invalid."""


@dataclass(frozen=True)
class GenerationContext:
    """Manifest values needed to organize raw objects."""

    school_year: str
    synthetic_data: bool


@dataclass(frozen=True)
class DiscoveredSourceFile:
    """A file matched to exactly one configured source contract."""

    path: Path
    source_name: str
    source_system: str

    @property
    def filename(self) -> str:
        """Return the original basename unchanged."""

        return self.path.name

    @property
    def file_size_bytes(self) -> int:
        """Return the source file size without modifying the file."""

        return self.path.stat().st_size


def load_generation_context(input_dir: Path) -> GenerationContext:
    """Read and validate the generated-file manifest used by raw ingestion."""

    manifest_path = input_dir / "generation_manifest.json"
    try:
        raw_manifest: Any = json.loads(manifest_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise DiscoveryError(
            f"Unable to read generated manifest {manifest_path}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise DiscoveryError(f"Generated manifest is invalid JSON: {manifest_path}") from error

    if not isinstance(raw_manifest, dict):
        raise DiscoveryError("Generated manifest must contain a JSON object")
    arguments = raw_manifest.get("arguments")
    if not isinstance(arguments, dict):
        raise DiscoveryError("Generated manifest must contain an arguments object")
    school_year = arguments.get("school_year")
    if not isinstance(school_year, str) or len(school_year) != 9 or school_year[4] != "-":
        raise DiscoveryError("Generated manifest school_year must use YYYY-YYYY")
    synthetic_data = raw_manifest.get("synthetic_data")
    if synthetic_data is not True:
        raise DiscoveryError("Raw demo ingestion requires a manifest labeled synthetic_data=true")
    return GenerationContext(school_year=school_year, synthetic_data=True)


def _selected_contracts(
    configuration: ConfigurationBundle,
    source: str,
) -> list[SourceContract]:
    enabled_systems = {
        system.name for system in configuration.source_systems.source_systems if system.enabled
    }
    enabled_contracts = [
        contract
        for contract in configuration.contracts.values()
        if contract.source_system in enabled_systems
    ]
    if source == "all":
        return enabled_contracts

    selected = [
        contract
        for contract in enabled_contracts
        if contract.source_name == source or contract.source_system == source
    ]
    if not selected:
        available = sorted(
            {
                value
                for contract in enabled_contracts
                for value in (contract.source_name, contract.source_system)
            }
        )
        raise DiscoveryError(
            f"Unknown or disabled source {source!r}; available values: {', '.join(available)}"
        )
    return selected


def discover_source_files(
    input_dir: Path,
    configuration: ConfigurationBundle,
    source: str = "all",
) -> list[DiscoveredSourceFile]:
    """Discover contract-matched files in a local directory."""

    if not input_dir.is_dir():
        raise DiscoveryError(f"Input directory does not exist or is not a directory: {input_dir}")

    discovered_by_path: dict[Path, DiscoveredSourceFile] = {}
    for contract in _selected_contracts(configuration, source):
        for path in sorted(input_dir.glob(contract.file_pattern)):
            if not path.is_file():
                continue
            resolved_path = path.resolve()
            if resolved_path in discovered_by_path:
                existing = discovered_by_path[resolved_path]
                raise DiscoveryError(
                    f"{path} matches multiple contracts: "
                    f"{existing.source_name} and {contract.source_name}"
                )
            discovered_by_path[resolved_path] = DiscoveredSourceFile(
                path=path,
                source_name=contract.source_name,
                source_system=contract.source_system,
            )

    return sorted(
        discovered_by_path.values(),
        key=lambda source_file: (source_file.source_system, source_file.filename),
    )

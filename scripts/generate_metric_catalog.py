"""Render the governed metric configuration as a Markdown catalog."""

from __future__ import annotations

import argparse
from pathlib import Path

from k12hub.contracts import MetricsConfig, load_yaml_model


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_metric_catalog(configuration: MetricsConfig) -> str:
    """Return deterministic Markdown containing every governed metric field."""

    lines = [
        "# Metric catalog",
        "",
        "This catalog is generated from `config/metrics.yml` "
        f"(schema `{configuration.schema_version}`).",
        "",
        "Rates use safe division and remain null when their denominator or required evidence is "
        "missing. Synthetic attendance and chronic-absence rate tests use an absolute rounding "
        "tolerance of `0.000001`; count and instructional-day comparisons must match exactly.",
        "",
        "| Metric | Description | Formula | Grain | Allowed dimensions | Source model | "
        "Refresh expectation | Privacy |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for metric in configuration.metrics:
        dimensions = ", ".join(metric.allowed_dimensions) or "None"
        values = (
            metric.name,
            metric.description,
            metric.formula,
            metric.grain,
            dimensions,
            metric.source_model,
            metric.refresh_expectation,
            metric.privacy_classification,
        )
        lines.append("| " + " | ".join(_cell(value) for value in values) + " |")
    lines.extend(
        [
            "",
            "The chronic-absence threshold is configured with the dbt variable "
            "`chronic_absence_threshold` and defaults to `0.10`. The reporting freshness SLA is "
            "configured with `source_freshness_sla_hours` and defaults to `24` hours.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    """Render the catalog to stdout or verify a checked-in catalog."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/metrics.yml"))
    parser.add_argument("--check", type=Path)
    arguments = parser.parse_args()
    configuration = load_yaml_model(arguments.config, MetricsConfig)
    rendered = render_metric_catalog(configuration)
    if arguments.check is not None:
        existing = arguments.check.read_text(encoding="utf-8")
        if existing != rendered:
            parser.error(f"{arguments.check} is not synchronized with {arguments.config}")
        return 0
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

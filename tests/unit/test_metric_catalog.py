"""Tests for the generated governed metric catalog."""

from pathlib import Path

from scripts.generate_metric_catalog import render_metric_catalog

from k12hub.contracts import MetricsConfig, load_yaml_model


def test_checked_in_metric_catalog_matches_configuration() -> None:
    configuration = load_yaml_model(Path("config/metrics.yml"), MetricsConfig)

    rendered = render_metric_catalog(configuration)

    assert Path("docs/metric_catalog.md").read_text(encoding="utf-8") == rendered
    assert all(metric.name in rendered for metric in configuration.metrics)

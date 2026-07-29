import json
import logging
from pathlib import Path

import k12hub
from k12hub.config import Environment, Settings
from k12hub.logging_config import JsonFormatter, configure_logging


def test_package_imports() -> None:
    assert k12hub.__version__ == "0.1.0"


def test_json_formatter_emits_structured_record() -> None:
    record = logging.LogRecord(
        name="k12hub.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="configuration ready",
        args=(),
        exc_info=None,
    )

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "k12hub.test"
    assert payload["message"] == "configuration ready"
    assert payload["timestamp"].endswith("+00:00")


def test_json_formatter_includes_ingestion_context() -> None:
    record = logging.LogRecord(
        name="k12hub.ingestion",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="file uploaded",
        args=(),
        exc_info=None,
    )
    record.pipeline_run_id = "00000000-0000-0000-0000-000000000001"
    record.source_filename = "students.csv"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["pipeline_run_id"] == "00000000-0000-0000-0000-000000000001"
    assert payload["source_filename"] == "students.csv"


def test_configure_logging_supports_plain_output() -> None:
    configure_logging(
        Settings(
            environment=Environment.TEST,
            log_level="WARNING",
            data_dir=Path("data/fixtures"),
            structured_logging=False,
        )
    )

    root_logger = logging.getLogger()
    assert root_logger.level == logging.WARNING
    assert len(root_logger.handlers) == 1

"""Verify connectivity to the local PostgreSQL and MinIO services."""

from __future__ import annotations

import logging

from k12hub.config import load_settings
from k12hub.logging_config import configure_logging
from k12hub.service_checks import ServiceCheckError, check_services


def main() -> int:
    """Run service checks and return a process exit code."""

    settings = load_settings()
    configure_logging(settings)
    logger = logging.getLogger(__name__)

    try:
        check_services(settings)
    except ServiceCheckError:
        logger.exception("Local infrastructure check failed")
        return 1

    logger.info("PostgreSQL and MinIO checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

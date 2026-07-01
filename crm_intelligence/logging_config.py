"""
Centralized logging configuration.

Call setup_logging() once at application startup.
All modules use: logger = logging.getLogger(__name__)
"""

import logging
import sys

from crm_intelligence.config import LOG_LEVEL


def setup_logging() -> None:
    """Configure application-wide logging."""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format=log_format,
        datefmt=date_format,
        stream=sys.stdout,
    )

    # Suppress noisy third-party loggers
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

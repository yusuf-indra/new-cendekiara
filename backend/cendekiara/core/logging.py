"""Logging setup for every entry point (API, worker, CLI). No `print` anywhere."""

from __future__ import annotations

import logging
import sys
from typing import TextIO

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


class StderrHandler(logging.StreamHandler[TextIO]):
    """Our own handler, so setup_logging() can replace it instead of piling up."""


def setup_logging(level: str = "INFO") -> None:
    """Send logs to stderr. Idempotent: calling it twice keeps a single handler."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if isinstance(handler, StderrHandler):
            root.removeHandler(handler)
    handler = StderrHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(handler)
    root.setLevel(level.strip().upper())

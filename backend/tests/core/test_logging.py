"""setup_logging() writes to stderr and can be called again without piling up."""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest

from cendekiara.core.logging import StderrHandler, setup_logging


@pytest.fixture
def root_logging() -> Iterator[None]:
    """Give the root logger back as it was."""
    root = logging.getLogger()
    handlers = list(root.handlers)
    level = root.level
    yield
    root.handlers = handlers
    root.setLevel(level)


def test_logs_go_to_stderr(root_logging: None, capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging("INFO")
    logging.getLogger("cendekiara.test").info("hello there")
    captured = capsys.readouterr()
    assert "hello there" in captured.err
    assert captured.out == ""


def test_setup_logging_is_idempotent(root_logging: None) -> None:
    setup_logging("INFO")
    setup_logging("INFO")
    ours = [handler for handler in logging.getLogger().handlers if isinstance(handler, StderrHandler)]
    assert len(ours) == 1


def test_setup_logging_sets_the_level(root_logging: None) -> None:
    setup_logging("error")
    assert logging.getLogger().level == logging.ERROR

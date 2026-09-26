"""Regression tests for structured logging privacy."""

import logging

import pytest

from app.utils.structured_logging import StructuredLogger


def test_failed_operation_does_not_log_exception_text(caplog):
    marker = "PATIENT-SECRET-MARKER"
    logger = StructuredLogger("test.structured_logging_privacy")
    caplog.set_level(logging.ERROR, logger="test.structured_logging_privacy")

    with pytest.raises(RuntimeError, match=marker):
        with logger.operation("test-operation"):
            raise RuntimeError(marker)

    assert marker not in caplog.text
    assert "error_type=RuntimeError" in caplog.text

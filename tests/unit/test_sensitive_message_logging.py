"""Regression tests preventing clinical payloads from entering application logs."""

import logging
from unittest.mock import Mock

import pytest

from app.services import pam_message_generation
from app.services.mfn_structure import process_mfn_message


def test_pam_generation_logs_only_technical_metadata(caplog, monkeypatch):
    marker = "PATIENT-SECRET-MARKER"
    monkeypatch.setattr(
        pam_message_generation,
        "generate_patient_message",
        lambda *_args, **_kwargs: "MSH|^~\\&|technical",
    )
    caplog.set_level(logging.DEBUG, logger="app.services.pam_message_generation")

    pam_message_generation.generate_pam_hl7(
        {"family": marker},
        "patient",
        Mock(),
    )

    assert marker not in caplog.text
    assert "entity_type=patient" in caplog.text


def test_mfn_import_does_not_log_raw_message_or_segments(caplog):
    marker = "PATIENT-SECRET-MARKER"
    caplog.set_level(logging.DEBUG, logger="app.services.mfn_structure")

    with pytest.raises(ValueError):
        process_mfn_message(f"{marker}|not-a-valid-mfn", Mock())

    assert marker not in caplog.text
    assert "processing message bytes=" in caplog.text

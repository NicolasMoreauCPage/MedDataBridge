"""Regression tests for safe errors returned by example import routes."""

from io import BytesIO
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, UploadFile

from app.routers import import_examples


def _raise_import_error(*_args, **_kwargs):
    raise RuntimeError("SENSITIVE-INTERNAL-DETAIL")


def test_structure_import_hides_internal_exception_detail(monkeypatch):
    monkeypatch.setattr(import_examples, "_resolve_ej_in_ght", lambda *_args: Mock())
    monkeypatch.setattr(
        import_examples,
        "_load_import_impls",
        lambda: (_raise_import_error, Mock()),
    )
    upload = UploadFile(filename="structure.hl7", file=BytesIO(b"MSH|test"))

    with pytest.raises(HTTPException) as error:
        import_examples.import_structure_mfn_endpoint(1, 1, upload, Mock())

    assert error.value.status_code == 500
    assert error.value.detail == "Erreur interne pendant l'import de structure MFN"
    assert "SENSITIVE-INTERNAL-DETAIL" not in error.value.detail


def test_pam_import_hides_internal_exception_detail(monkeypatch):
    monkeypatch.setattr(import_examples, "_resolve_ej", lambda *_args: Mock())
    monkeypatch.setattr(
        import_examples,
        "_load_import_impls",
        lambda: (Mock(), _raise_import_error),
    )
    upload = UploadFile(filename="admission.hl7", file=BytesIO(b"MSH|test"))

    with pytest.raises(HTTPException) as error:
        import_examples.import_pam_messages_endpoint(1, [upload], Mock())

    assert error.value.status_code == 500
    assert error.value.detail == "Erreur interne pendant l'import des messages PAM"
    assert "SENSITIVE-INTERNAL-DETAIL" not in error.value.detail

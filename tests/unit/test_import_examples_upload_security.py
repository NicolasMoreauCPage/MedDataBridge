"""Security tests for the temporary PAM upload staging area."""

from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.routers.import_examples import _read_upload_limited, _safe_pam_upload_destination


@pytest.mark.parametrize(
    "filename",
    [
        "../../outside.hl7",
        "nested/outside.hl7",
        "..\\..\\outside.hl7",
        "C:\\temp\\outside.hl7",
        "/tmp/outside.hl7",
        "invalid\x00name.hl7",
    ],
)
def test_pam_upload_destination_rejects_client_paths(tmp_path: Path, filename: str):
    with pytest.raises(HTTPException) as error:
        _safe_pam_upload_destination(tmp_path, filename)

    assert error.value.status_code == 400


def test_pam_upload_destination_is_server_generated_and_contained(tmp_path: Path):
    destination = _safe_pam_upload_destination(tmp_path, "admission.hl7")

    assert destination.parent == tmp_path.resolve()
    assert destination.suffix == ".hl7"
    assert destination.name != "admission.hl7"


def test_upload_reader_rejects_the_first_byte_above_the_limit():
    with pytest.raises(HTTPException) as error:
        _read_upload_limited(BytesIO(b"abcdef"), max_size=5)

    assert error.value.status_code == 413


def test_upload_reader_preserves_content_within_limit():
    assert _read_upload_limited(BytesIO(b"abcde"), max_size=5) == b"abcde"

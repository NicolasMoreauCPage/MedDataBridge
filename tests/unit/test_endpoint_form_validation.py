import pytest
from fastapi import HTTPException

from app.routers.endpoints import _parse_optional_form_id


def test_endpoint_form_accepts_a_blank_optional_identifier():
    assert _parse_optional_form_id("  ", "ght_context_id") is None


def test_endpoint_form_rejects_an_invalid_identifier():
    with pytest.raises(HTTPException) as raised:
        _parse_optional_form_id("not-an-id", "linked_endpoint_id")

    assert raised.value.status_code == 422
    assert raised.value.detail == "Le champ linked_endpoint_id doit être un entier valide."

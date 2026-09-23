import pytest
from fastapi import HTTPException

from app.routers.venues import _parse_venue_filter_date


def test_venue_filter_accepts_date_and_datetime_values():
    assert _parse_venue_filter_date("2026-09-23", "start_from").date().isoformat() == "2026-09-23"
    assert _parse_venue_filter_date("2026-09-23T14:30:00", "start_to").hour == 14


def test_venue_filter_rejects_invalid_dates():
    with pytest.raises(HTTPException) as raised:
        _parse_venue_filter_date("not-a-date", "start_from")

    assert raised.value.status_code == 422
    assert raised.value.detail == "Le filtre start_from doit être une date ISO 8601 valide."

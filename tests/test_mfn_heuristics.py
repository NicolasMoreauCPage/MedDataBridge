import pytest

from app.services.mfn_structure import _normalize_loc_type, _extract_type_and_identifier_from_loc, _extract_identifier_from_loc


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("service", "D"),
        ("Service", "D"),
        ("pôle", "P"),
        ("UF", "UF"),
        ("lit", "B"),
        ("Chambre", "R"),
        ("etablissement geographique", "ETBL_GRPQ"),
    ],
)
def test_normalize_loc_type_basic(raw, expected):
    assert _normalize_loc_type(raw) == expected


def test_extract_type_and_identifier_from_loc():
    raw = "^^^^^D^^^^0192&CPAGE&700004591&FINEJ"
    t, ident = _extract_type_and_identifier_from_loc(raw)
    assert t == "D"
    assert ident == "0192"


def test_extract_identifier_from_loc():
    raw = "^^^^^ETBL_GRPQ^^^^75&CPAGE&..."
    ident = _extract_identifier_from_loc(raw)
    assert ident == "75"

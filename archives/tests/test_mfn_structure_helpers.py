import pytest
from app.services.mfn_structure import (
    _normalize_loc_type,
    _extract_identifier_from_loc,
    _extract_type_and_identifier_from_loc,
    extract_location_type,
    parse_location_characteristics,
    clean_hl7_date,
    format_datetime
)


def test_normalize_loc_type_basic():
    assert _normalize_loc_type("Service") == "D"
    assert _normalize_loc_type("pôle") == "P"
    assert _normalize_loc_type("lit") == "B"
    assert _normalize_loc_type("") == ""


def test_extract_identifier_from_loc():
    raw = "^^^^^D^^^^0192&CPAGE&700004591&FINEJ"
    assert _extract_identifier_from_loc(raw) == "0192"
    raw2 = "^^^^^ETBL_GRPQ^^^^75&CPAGE" 
    assert _extract_identifier_from_loc(raw2) == "75"


def test_extract_type_and_identifier_from_loc():
    raw = "^^^^^P^^^^123&CPAGE"
    t, ident = _extract_type_and_identifier_from_loc(raw)
    assert t == "P" and ident == "123"


def test_extract_location_type_segment():
    # LOC|^^^^^D^^^^0192&CPAGE&700004591&FINEJ||D|Service
    seg = ["LOC", "^^^^^D^^^^0192&CPAGE&700004591&FINEJ", "", "", "D", "Service"]
    t, ident = extract_location_type(seg)
    assert t == "D" and ident == "0192"


def test_parse_location_characteristics():
    # Example LCH|1|...|...|ID_GLBL^...|12345^^^||
    segs = [
        ["LCH", "", "", "", "ID_GLBL^...", "12345^^^"],
        ["LCH", "", "", "", "LBL", "Laboratoire^^^"],
    ]
    chars = parse_location_characteristics(segs)
    assert chars["ID_GLBL"] == "12345" and chars["LBL"] == "Laboratoire"


def test_clean_and_format_date():
    assert clean_hl7_date("") is None
    assert clean_hl7_date("20250101") == "20250101"
    assert format_datetime(None) == ""
    assert format_datetime("20250101") == "20250101"

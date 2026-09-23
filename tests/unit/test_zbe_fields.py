from app.services.zbe_fields import build_xon_unit, derive_zbe_nature


def test_xon_unit_exposes_the_code_in_first_and_tenth_components():
    value = build_xon_unit("UF-42", "Unité de soins")

    assert value.split("^")[0] == "Unité de soins"
    assert value.split("^")[9] == "UF-42"


def test_zbe_nature_uses_hospitalisation_as_safe_fallback():
    assert derive_zbe_nature("A01", "not-a-nature") == "H"

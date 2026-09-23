from app.services.hl7_fields import build_adt_header, build_patient_name, build_xad, to_hl7_administrative_sex


def test_patient_name_adds_distinct_birth_name_as_legal_repetition():
    assert build_patient_name("Durand", "Alice", birth_family="Martin") == "Durand^Alice^^^^^D~Martin^Alice^^^^^L"


def test_patient_name_does_not_duplicate_identical_legal_name():
    assert build_patient_name("Durand", "Alice", birth_family="Durand") == "Durand^Alice^^^^^L"


def test_xad_preserves_intermediate_empty_components_and_address_type():
    assert build_xad("1 rue de Paris", "", "Lyon", "", "69000", "FR", "H") == "1 rue de Paris^^Lyon^^69000^FR^H"


def test_adt_header_and_administrative_sex_follow_the_french_hl7_profile():
    msh, evn = build_adt_header("20260923120000", "A28", "ADT_A05", "control-1")

    assert msh == "MSH|^~\\&|POC|HOSP|EXT|HOSP|20260923120000||ADT^A28^ADT_A05|control-1|P|2.5^FRA^2.11|||||FRA|8859/1"
    assert evn == "EVN|A28|20260923120000"
    assert to_hl7_administrative_sex("other") == "U"

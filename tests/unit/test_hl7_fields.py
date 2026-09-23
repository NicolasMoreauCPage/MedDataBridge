from app.services.hl7_fields import build_patient_name, build_xad


def test_patient_name_adds_distinct_birth_name_as_legal_repetition():
    assert build_patient_name("Durand", "Alice", birth_family="Martin") == "Durand^Alice^^^^^D~Martin^Alice^^^^^L"


def test_patient_name_does_not_duplicate_identical_legal_name():
    assert build_patient_name("Durand", "Alice", birth_family="Durand") == "Durand^Alice^^^^^L"


def test_xad_preserves_intermediate_empty_components_and_address_type():
    assert build_xad("1 rue de Paris", "", "Lyon", "", "69000", "FR", "H") == "1 rue de Paris^^Lyon^^69000^FR^H"

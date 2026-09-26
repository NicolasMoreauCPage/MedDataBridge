from app.services.hprim.hprim_validator import HprimValidator


def test_hprim_schema_guessing_rejects_doctype_with_external_entity():
    xml = """<!DOCTYPE evenementsServeurActes [
        <!ENTITY external SYSTEM \"file:///etc/passwd\">
    ]>
    <evenementsServeurActes>&external;</evenementsServeurActes>"""

    assert HprimValidator().guess_schema_name(xml) is None


def test_hprim_schema_guessing_keeps_accepting_regular_document():
    assert (
        HprimValidator().guess_schema_name("<evenementsServeurActes />")
        == "evenements_serveur_actes"
    )

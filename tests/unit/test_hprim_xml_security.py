from app.services.hprim.hprim_validator import HprimValidator
from app.services.hprim.hprim_xml import HprimXmlService
import pytest


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


def test_hprim_service_rejects_doctype_before_parsing_message():
    xml = """<!DOCTYPE evenementsServeurActes [
        <!ENTITY internal "value">
    ]>
    <evenementsServeurActes>&internal;</evenementsServeurActes>"""

    with pytest.raises(ValueError, match="DOCTYPE XML interdite"):
        HprimXmlService().parse_xml(xml)

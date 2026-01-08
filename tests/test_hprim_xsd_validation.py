from app.services.hprim.hprim_validator import HprimValidator


def test_hprim_xsd_validation_evenements():
    """Validate minimal HPRIM XML (2.4) against official XSD."""
    xml = (
        '<?xml version="1.0" encoding="ISO-8859-1"?>\n'
        '<evenementsServeurActes version="2.4" acquittementAttendu="non" identifiantAttendu="non"'
        ' xmlns="http://www.hprim.org/hprimXML" xmlns:insee="http://www.hprim.org/inseeXML">\n'
        '  <enteteMessage modeTraitement="réel">\n'
        '    <identifiantMessage>TEST001</identifiantMessage>\n'
        '  </enteteMessage>\n'
        '</evenementsServeurActes>'
    )

    validator = HprimValidator()
    ok, errors = validator.validate_xml_string(xml, schema_name='evenements_serveur_actes')
    assert not ok
    assert errors and any(e.startswith("XSD Error:") for e in errors)

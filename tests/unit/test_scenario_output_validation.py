from app.services.scenario_output_validation import validate_compiled_payload
from app.services.pam_validation import validate_pam


def test_output_validator_reports_invalid_hl7_base_fields():
    report = validate_compiled_payload("MSH|^~\\&|||||||ORU^R01|||", "hl7")

    assert report.valid is False
    assert report.status == "invalid"
    assert any("MSH-10" in error for error in report.errors)
    assert any("MSH-12" in error for error in report.errors)


def test_pam_fr_accepts_recommended_8859_1_without_warning():
    message = (
        "MSH|^~\\&|S|F|R|F|202601010101||ADT^A28^ADT_A05|MSG1|P|2.5^FRA^2.11|||||FRA|8859/1\r"
        "PID|||123^^^S&1.2.3&ISO^PI||DUPONT^ALICE||19900101|F"
    )
    result = validate_pam(message, direction="out")

    assert not any(issue.code in {"MSH18_LEGACY", "MSH18_INVALID"} for issue in result.issues)
def test_output_validator_accepts_well_formed_generic_xml_with_warning():
    report = validate_compiled_payload("<document><value>ok</value></document>", "xml")

    assert report.valid is True
    assert report.status == "warning"
    assert report.warnings


def test_output_validator_rejects_xml_doctype():
    payload = """<!DOCTYPE document [
        <!ENTITY external SYSTEM "file:///etc/passwd">
    ]>
    <document>&external;</document>"""

    report = validate_compiled_payload(payload, "xml")

    assert report.valid is False
    assert report.errors == ["XML invalide: DOCTYPE XML interdite"]

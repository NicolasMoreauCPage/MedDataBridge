from app.models_structure import IdentifierNamespace
from app.services.scenario_identifier_replacer import replace_identifiers_in_hl7_message


def test_replaces_pid18_and_pv119_with_the_same_generated_nda(session):
    ipp = IdentifierNamespace(name="IPP", system="urn:oid:1.2.3", oid="1.2.3", type="IPP")
    nda = IdentifierNamespace(name="NDA", system="urn:oid:1.2.4", oid="1.2.4", type="NDA")
    venue = IdentifierNamespace(name="VEN", system="urn:oid:1.2.5", oid="1.2.5", type="VN")
    session.add_all([ipp, nda, venue])
    session.commit()
    message = (
        "MSH|^~\\&|SRC|FAC|DST|FAC|202601010000||ADT^A01|OLD|P|2.5\r"
        "PID|||OLD-IPP|||||||||||||||OLD-NDA\r"
        "PV1||I|||||||||||||||||OLD-VISIT"
    )

    compiled, ids = replace_identifiers_in_hl7_message(
        message, session, ipp, nda, venue, generated_ids={"ipp": "IPP-NEW", "nda": "NDA-NEW", "venue": "VEN-NEW"}
    )

    pid = next(line for line in compiled.split("\r") if line.startswith("PID| ".strip()))
    pv1 = next(line for line in compiled.split("\r") if line.startswith("PV1|"))
    assert pid.split("|")[18] == "NDA-NEW^^^NDA&1.2.4&ISO^AN"
    assert pv1.split("|")[19] == "VEN-NEW^^^VEN&1.2.5&ISO^VN"
    assert ids["nda"] == "NDA-NEW"

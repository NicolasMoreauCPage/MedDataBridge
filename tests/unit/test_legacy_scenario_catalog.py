from sqlmodel import select

from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.services.legacy_scenario_catalog import import_legacy_catalog


def test_import_catalog_deduplicates_and_splits_legacy_hprim_xml(session):
    catalog = [
        {
            "key": "pam-a", "name": "PAM A", "category": "IHE_PAM", "protocol": "HL7",
            "steps": [{"order_index": 1, "message_format": "hl7", "payload": "MSH|A"}],
        },
        {
            "key": "pam-a-copy", "name": "PAM A copy", "category": "IHE_PAM", "protocol": "HL7",
            "steps": [{"order_index": 1, "message_format": "hl7", "payload": "MSH|A"}],
        },
        {
            "key": "hprim-a", "name": "Acte CCAM", "category": "HPRIM", "protocol": "HPRIM",
            "steps": [{"order_index": 1, "message_format": "hprimxml", "payload": "MSH|préambule\nMSH|<?xml version=\"1.0\"?><acte><ipp>$NIP$</ipp></acte>"}],
        },
    ]
    report = import_legacy_catalog(session, catalog)

    assert report == {"source_items": 3, "scenarios": 2, "created": 2, "updated": 0, "duplicates": 1}
    scenarios = session.exec(select(InteropScenario).where(InteropScenario.source_checksum.is_not(None))).all()
    assert len(scenarios) == 2
    hprim = next(item for item in scenarios if item.category == "HPRIM")
    step = session.exec(select(InteropScenarioStep).where(InteropScenarioStep.scenario_id == hprim.id)).one()
    assert step.message_format == "xml"
    assert step.payload.startswith("<?xml")
    assert "{{patient.ipp}}" in step.payload

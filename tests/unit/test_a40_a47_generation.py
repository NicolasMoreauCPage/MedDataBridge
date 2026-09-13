"""Régressions de génération HL7 v2.5 pour les transactions A40/A47."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from adapters.hl7_pam_fr import build_message_for_movement
from app.models import Dossier, Patient
from app.models_identifiers import Identifier, IdentifierType
from app.services.hl7_generator import (
    generate_patient_identifier_change_message,
    generate_patient_merge_message,
)
from app.services.pam_validation import validate_pam


def _patient_and_dossier(session):
    patient = Patient(patient_seq=9101, identifier="IPP-NEW", family="DUPONT", given="Anne", gender="F")
    session.add(patient)
    session.flush()
    session.add(
        Identifier(
            value="IPP-NEW",
            system="HOSP",
            type=IdentifierType.IPP,
            status="active",
            patient_id=patient.id,
        )
    )
    dossier = Dossier(
        dossier_seq=9101,
        patient_id=patient.id,
        admit_time=datetime.now(timezone.utc),
    )
    session.add(dossier)
    session.flush()
    return patient, dossier


@pytest.mark.parametrize(
    ("factory", "expected_event", "expected_structure", "prior_name"),
    [
        (generate_patient_merge_message, "A40", "ADT_A39", "DUPONT-ANCIEN^Anne"),
        (generate_patient_identifier_change_message, "A47", "ADT_A30", None),
    ],
)
def test_generic_generator_emits_conformant_identity_mrg_message(
    session, factory, expected_event, expected_structure, prior_name
):
    patient, dossier = _patient_and_dossier(session)
    kwargs = {
        "patient": patient,
        "dossier": dossier,
        "prior_patient_identifiers": ["IPP-OLD^^^HOSP^PI", "INS-OLD^^^INS&1.2.250.1.213.1.4.8&ISO^PI"],
        "session": session,
        "timestamp": datetime(2026, 9, 13, 10, 30, tzinfo=timezone.utc),
        "control_id": f"TEST-{expected_event}",
    }
    if prior_name:
        kwargs["prior_patient_name"] = prior_name
    message = factory(**kwargs)

    segments = message.split("\r")
    assert segments[0].split("|")[8] == f"ADT^{expected_event}^{expected_structure}"
    assert segments[1] == f"EVN|{expected_event}|20260913103000"
    assert segments[2].startswith("PID|")
    assert segments[3].startswith("MRG|IPP-OLD^^^HOSP^PI~INS-OLD^^^INS&1.2.250.1.213.1.4.8&ISO^PI")
    assert not any(segment.startswith(("PV1|", "ZBE|")) for segment in segments)
    if prior_name:
        assert segments[3].endswith(prior_name)
    else:
        assert segments[3] == "MRG|IPP-OLD^^^HOSP^PI~INS-OLD^^^INS&1.2.250.1.213.1.4.8&ISO^PI||||||"

    result = validate_pam(message, direction="out")
    assert result.is_valid, [issue.message for issue in result.issues]


@pytest.mark.parametrize("factory", [generate_patient_merge_message, generate_patient_identifier_change_message])
@pytest.mark.parametrize("prior_identifiers", [[], ["~"]])
def test_generic_generator_rejects_missing_mrg1(session, factory, prior_identifiers):
    patient, dossier = _patient_and_dossier(session)

    with pytest.raises(ValueError, match="MRG-1"):
        factory(patient=patient, dossier=dossier, prior_patient_identifiers=prior_identifiers, session=session)


def test_adapter_a40_uses_identity_structure_without_movement_segments():
    patient = SimpleNamespace(identifier="IPP-NEW", family="DUPONT", given="Anne", birth_date="19800101", gender="F")
    venue = SimpleNamespace(patient_class="I", code="UF01", hospital_service="MED", visit_number="V1")
    dossier = SimpleNamespace(uf_responsabilite="UF01")
    movement = SimpleNamespace(
        type="A40",
        mouvement_seq="M-40",
        merge_identifiers="IPP-OLD^^^HOSP^PI",
        previous_name="DUPONT-ANCIEN^Anne",
    )

    message = build_message_for_movement(dossier=dossier, venue=venue, movement=movement, patient=patient)

    segments = message.split("\r")
    assert segments[0].split("|")[8] == "ADT^A40^ADT_A39"
    assert any(segment.startswith("MRG|IPP-OLD^^^HOSP^PI") for segment in segments)
    assert not any(segment.startswith(("PV1|", "ZBE|")) for segment in segments)


def test_adapter_rejects_a47_without_mrg1():
    patient = SimpleNamespace(identifier="IPP-NEW", family="DUPONT", given="Anne")
    venue = SimpleNamespace(patient_class="I", code="UF01", hospital_service="MED", visit_number="V1")
    dossier = SimpleNamespace(uf_responsabilite="UF01")
    movement = SimpleNamespace(type="A47", mouvement_seq="M-47")

    with pytest.raises(ValueError, match="MRG-1"):
        build_message_for_movement(dossier=dossier, venue=venue, movement=movement, patient=patient)

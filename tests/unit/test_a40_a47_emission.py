import pytest
from datetime import datetime, timezone
from sqlmodel import select
from app.models import Patient, Dossier
from app.models_identifiers import Identifier, IdentifierType
from app.services.patient_merge import merge_patients, change_patient_identifier
from app.services.emit_on_create import generate_pam_hl7


def test_merge_patients_reassigns_dossiers_and_archives_source(session):
    survivor = Patient(patient_seq=1, identifier="IPP001", family="DOE", given="JOHN")
    source = Patient(patient_seq=2, identifier="IPP002", family="DOE", given="JOHNNY")
    session.add(survivor)
    session.add(source)
    session.flush()

    dossier = Dossier(dossier_seq=1, patient_id=source.id, admit_time=datetime.now(timezone.utc))
    session.add(dossier)
    ident = Identifier(value="IPP002", system="HOSP", type=IdentifierType.IPP, status="active", patient_id=source.id)
    session.add(ident)
    session.flush()

    ok, err = merge_patients(session, source.id, survivor.id)
    assert ok, err

    session.refresh(dossier)
    assert dossier.patient_id == survivor.id

    session.refresh(source)
    assert source.family.startswith("[MERGED]")
    assert source.identifier.startswith("ARCHIVED-")

    session.refresh(ident)
    assert ident.status == "old"
    assert ident.patient_id == survivor.id


def test_change_patient_identifier_updates_and_marks_old(session):
    patient = Patient(patient_seq=3, identifier="IPP003", family="MARTIN", given="ALICE")
    session.add(patient)
    session.flush()
    old_ident = Identifier(value="IPP003", system="HOSP", type=IdentifierType.IPP, status="active", patient_id=patient.id)
    session.add(old_ident)
    session.flush()

    ok, err = change_patient_identifier(session, patient.id, "IPP003-NEW", new_system="HOSP")
    assert ok, err

    session.refresh(patient)
    assert patient.identifier == "IPP003-NEW"

    session.refresh(old_ident)
    assert old_ident.status == "old"

    new_ident = session.exec(
        select(Identifier).where(Identifier.patient_id == patient.id).where(Identifier.value == "IPP003-NEW")
    ).first()
    assert new_ident is not None
    assert new_ident.status == "active"


def test_generate_pam_hl7_merge_builds_a40_with_mrg():
    entity = {
        "id": 1, "patient_seq": 1, "identifier": "IPP001", "family": "DOE", "given": "JOHN",
        "gender": "M", "entite_juridique_id": None,
    }
    from unittest.mock import MagicMock
    fake_session = MagicMock()
    fake_session.exec.return_value.first.return_value = None
    msg = generate_pam_hl7(
        entity, "patient", fake_session, operation="merge",
        mrg_prior_identifiers=["IPP002^^^HOSP^PI"],
    )
    segments = msg.split("\r")
    assert any(s.startswith("MSH") and "A40" in s and "ADT_A39" in s for s in segments)
    assert any(s.startswith("MRG|IPP002^^^HOSP^PI") for s in segments)
    assert not any(s.startswith("PV1") for s in segments)


def test_generate_pam_hl7_change_id_builds_a47_with_mrg():
    entity = {
        "id": 1, "patient_seq": 1, "identifier": "IPP001-NEW", "family": "DOE", "given": "JOHN",
        "gender": "M", "entite_juridique_id": None,
    }
    from unittest.mock import MagicMock
    fake_session = MagicMock()
    fake_session.exec.return_value.first.return_value = None
    msg = generate_pam_hl7(
        entity, "patient", fake_session, operation="change_id",
        mrg_prior_identifiers=["IPP001-OLD^^^HOSP^PI"],
    )
    segments = msg.split("\r")
    assert any(s.startswith("MSH") and "A47" in s and "ADT_A30" in s for s in segments)
    assert any(s.startswith("MRG|IPP001-OLD^^^HOSP^PI") for s in segments)

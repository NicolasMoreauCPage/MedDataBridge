"""Regression coverage for persistent outgoing HPRIM logs."""

from datetime import datetime, timezone

from sqlmodel import select

from app.models import Dossier, Patient, UCDAct
from app.models_shared import EndpointKind, EndpointRole, MessageLog, SystemEndpoint
from app.services.emit_on_create import emit_to_senders_async


def test_hprim_emission_persists_a_valid_message_log(session):
    endpoint = SystemEndpoint(
        name="HPRIM test sender",
        kind=EndpointKind.HPRIM,
        role=EndpointRole.SENDER,
        emit_hprim_ucd=True,
    )
    patient = Patient(identifier="IPP-HPRIM-1", family="DUPONT", given="Alice", gender="female")
    session.add_all([endpoint, patient])
    session.flush()

    dossier = Dossier(dossier_seq=91001, patient_id=patient.id, admit_time=datetime.now(timezone.utc))
    session.add(dossier)
    session.flush()

    act = UCDAct(
        dossier_id=dossier.id,
        code_ucd="3400936050501",
        denomination_libelle="DOLIPRANE 1000MG",
        quantite=1,
        montant_unitaire_facture_ttc=4.5,
        execute_date=datetime.now(timezone.utc),
    )
    session.add(act)
    session.flush()

    emit_to_senders_async(act, "ucd_act", session)

    log = session.exec(
        select(MessageLog).where(MessageLog.endpoint_id == endpoint.id)
    ).one()
    assert log.direction == "out"
    assert log.kind == "HPRIM"
    assert log.status == "pending"
    assert "DUPONT" in log.payload

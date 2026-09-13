"""Tests des actions groupées de l'atelier de cotations."""

from datetime import datetime

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import CCAMAct, Dossier, LPPAct, NGAPAct, Patient, UCDAct


def _dossier(session: Session) -> Dossier:
    patient = Patient(identifier="COT-BULK", nom="TEST", prenom="ACTES", date_naissance="1980-01-01", sexe="F")
    session.add(patient)
    session.commit()
    session.refresh(patient)
    dossier = Dossier(patient_id=patient.id, dossier_seq=98101, admit_time=datetime.now(), current_state="OPEN")
    session.add(dossier)
    session.commit()
    session.refresh(dossier)
    return dossier


def test_bulk_actions_update_boolean_statuses_for_every_cotation_type(client: TestClient, session: Session) -> None:
    dossier = _dossier(session)
    now = datetime(2026, 1, 2, 10, 0)
    acts = [
        CCAMAct(dossier_id=dossier.id, code_acte="HBMD001", code_activite="01", code_phase="01", execute_date=now),
        NGAPAct(dossier_id=dossier.id, lettre_cle="AMI", coefficient=1, execute_date=now),
        UCDAct(dossier_id=dossier.id, code_ucd="3400935001324", denomination_libelle="Produit UCD", quantite=1, execute_date=now),
        LPPAct(dossier_id=dossier.id, code_lpp="1234567890123", denomination_libelle="Produit LPP", montant_unitaire_facture_ttc=10, quantite=1, execute_date=now),
    ]
    for acte in acts:
        session.add(acte)
    session.commit()
    for acte in acts:
        session.refresh(acte)

    selection = [
        {"type": "ccam", "id": acts[0].id},
        {"type": "ngap", "id": acts[1].id},
        {"type": "ucd", "id": acts[2].id},
        {"type": "lpp", "id": acts[3].id},
    ]
    validated = client.post("/cotations/api/bulk", json={"action": "validate", "actes": selection})
    assert validated.status_code == 200
    invoiced = client.post("/cotations/api/bulk", json={"action": "invoice", "actes": selection})
    assert invoiced.status_code == 200

    session.expire_all()
    for model, acte in zip((CCAMAct, NGAPAct, UCDAct, LPPAct), acts):
        stored = session.get(model, acte.id)
        assert stored is not None
        assert stored.valide is True
        assert stored.facture is True


def test_bulk_actions_reject_unknown_cotation_type(client: TestClient) -> None:
    response = client.post("/cotations/api/bulk", json={"action": "invoice", "actes": [{"type": "unknown", "id": 1}]})
    assert response.status_code == 400

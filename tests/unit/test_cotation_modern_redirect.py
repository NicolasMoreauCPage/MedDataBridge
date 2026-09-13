"""Le point d'entrée historique de cotation mène vers le workspace actif."""

from datetime import datetime

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Dossier, Patient


def test_cotation_modern_redirects_to_persistent_workspace(client: TestClient, session: Session) -> None:
    patient = Patient(identifier="COT-MODERN", nom="TEST", prenom="REDIRECT", date_naissance="1980-01-01", sexe="F")
    session.add(patient)
    session.commit()
    session.refresh(patient)
    dossier = Dossier(patient_id=patient.id, dossier_seq=98110, admit_time=datetime.now(), current_state="OPEN")
    session.add(dossier)
    session.commit()
    session.refresh(dossier)

    response = client.get(f"/cotation-modern/dossiers/{dossier.id}/cotation", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/cotations/dossier/{dossier.id}/saisie"

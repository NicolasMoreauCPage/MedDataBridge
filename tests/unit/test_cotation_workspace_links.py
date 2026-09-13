from pathlib import Path
from datetime import datetime

from app.models import Dossier, Patient


def test_active_cotation_links_target_the_persistent_workspace() -> None:
    templates = {
        "dossier_detail.html": "{{ dossier.id }}",
        "messages_by_dossier.html": "{{ d.dossier_id }}",
    }
    for template_name, dossier_expression in templates.items():
        template = Path("app/templates", template_name).read_text(encoding="utf-8")

        assert f"/dossiers/{dossier_expression}/cotations" not in template
        assert f"/cotations/dossier/{dossier_expression}/saisie" in template


def test_ccam_dashboard_advertises_the_persistent_workspace() -> None:
    source = Path("app/routers/ccam.py").read_text(encoding="utf-8")

    assert '"url": "/cotations/dossier/{dossier_id}/saisie"' in source


def test_legacy_cotation_url_redirects_to_the_persistent_workspace(client, session) -> None:
    patient = Patient(identifier="COT-LINK", nom="TEST", prenom="LIEN", date_naissance="1980-01-01", sexe="F")
    session.add(patient)
    session.flush()
    dossier = Dossier(patient_id=patient.id, dossier_seq=98111, admit_time=datetime.now(), current_state="OPEN")
    session.add(dossier)
    session.commit()
    session.refresh(dossier)

    response = client.get(f"/dossiers/{dossier.id}/cotations", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == f"/cotations/dossier/{dossier.id}/saisie"

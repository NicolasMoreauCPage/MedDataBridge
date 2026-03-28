from fastapi.testclient import TestClient
from sqlmodel import select

from app.models.hprim_models import HprimCCAMAct, HprimNGAPAct, HprimMessage


def _ccam_act_payload(commentaire: str = "acte-test"):
    return {
        "code_acte": "HBMD001",
        "code_activite": "01",
        "code_phase": "01",
        "executant_rpps": "12345678901",
        "date_execution": "2026-03-27T10:00:00",
        "quantite": 1,
        "modificateurs": ["A"],
        "montant": 50.0,
        "commentaire": commentaire,
    }


def _emission_payload(patient_id: str = "PAT-ROUNDTRIP"):
    return {
        "emetteur_id": "123456789",
        "emetteur_nom": "Hopital A",
        "destinataire_id": "987654321",
        "destinataire_nom": "Partenaire B",
        "patient": {
            "identifiant_id": patient_id,
            "identifiant_clef": "01",
            "nom": "DUPONT",
            "prenom": "ALICE",
        },
        "acteur": {
            "nom": "MARTIN",
            "prenom": "JEAN",
            "numero_rpps": "12345678901",
        },
        "actes": [_ccam_act_payload(commentaire="roundtrip")],
    }


def _ngap_act_payload(commentaire: str = "ngap-test"):
    return {
        "lettre_cle": "AMI",
        "coefficient": 2.5,
        "execute_date": "2026-03-27T12:00:00",
        "denombrement": 1,
        "position_dentaire": None,
        "execute_heure": "12:00",
        "numero_seance": 1,
        "nabms": [101, 202],
        "minor_major": "M",
        "montant": 33.5,
        "commentaire": commentaire,
        "bhn_phns": None,
    }


def _ngap_emission_payload(patient_id: str = "PAT-NGAP-EMIT"):
    return {
        "emetteur_id": "123456789",
        "emetteur_nom": "Hopital A",
        "destinataire_id": "987654321",
        "destinataire_nom": "Partenaire B",
        "patient": {
            "identifiant_id": patient_id,
            "identifiant_clef": "01",
            "nom": "DUPONT",
            "prenom": "ALICE",
        },
        "acteur": {
            "nom": "MARTIN",
            "prenom": "JEAN",
            "numero_rpps": "12345678901",
        },
        "actes": [_ngap_act_payload(commentaire="ngap-emission")],
        "dossier_id": "DOS-001",
    }


def test_hprim_ccam_crud_is_persisted(client: TestClient, session):
    response = client.post("/api/hprim/actes/ccam?patient_id=PAT-CRUD", json=_ccam_act_payload())
    assert response.status_code == 200
    body = response.json()
    acte_id = body["id"]

    stored = session.get(HprimCCAMAct, acte_id)
    assert stored is not None
    assert stored.patient_id == "PAT-CRUD"
    assert stored.code_acte == "HBMD001"

    get_response = client.get(f"/api/hprim/actes/ccam/{acte_id}")
    assert get_response.status_code == 200
    assert get_response.json()["commentaire"] == "acte-test"

    update_payload = _ccam_act_payload(commentaire="acte-modifie")
    update_payload["code_acte"] = "HBMD002"
    update_payload["code_activite"] = "02"
    update_payload["quantite"] = 2
    update_payload["modificateurs"] = ["B"]
    update_response = client.put(f"/api/hprim/actes/ccam/{acte_id}", json=update_payload)
    assert update_response.status_code == 200
    assert update_response.json()["code_acte"] == "HBMD002"

    history_response = client.get("/api/hprim/actes/ccam/patient/PAT-CRUD/historique")
    assert history_response.status_code == 200
    history_body = history_response.json()
    assert history_body["total"] == 1
    assert history_body["actes"][0]["id"] == acte_id

    delete_response = client.delete(f"/api/hprim/actes/ccam/{acte_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"

    history_after_delete = client.get("/api/hprim/actes/ccam/patient/PAT-CRUD/historique")
    assert history_after_delete.status_code == 200
    assert history_after_delete.json()["total"] == 0


def test_roundtrip_hprim_generate_download_reintegrate(client: TestClient, session):
    generate_response = client.post("/roundtrip-hprim/generate", json=_emission_payload())
    assert generate_response.status_code == 200
    generate_body = generate_response.json()
    assert generate_body["message_id"]
    assert generate_body["filename"].endswith(".xml")
    assert generate_body["validation_errors"] == []

    stored_message = session.get(HprimMessage, generate_body["message_id"])
    assert stored_message is not None
    assert stored_message.xml_size > 0
    assert stored_message.filename == generate_body["filename"]

    download_response = client.get(generate_body["download_url"])
    assert download_response.status_code == 200
    assert download_response.headers["content-type"].startswith("application/xml")
    assert "evenementsServeurActes" in download_response.text

    reintegrate_response = client.post(
        "/roundtrip-hprim/reintegrate",
        files={"file": (generate_body["filename"], download_response.content, "application/xml")},
    )
    assert reintegrate_response.status_code == 200
    reintegrate_body = reintegrate_response.json()
    assert reintegrate_body["status"] == "ok"
    assert reintegrate_body["actes_count"] == 1

    stored_acts = session.exec(
        select(HprimCCAMAct).where(HprimCCAMAct.patient_id == "PAT-ROUNDTRIP")
    ).all()
    assert len(stored_acts) >= 1


def test_hprim_ngap_crud_and_history(client: TestClient, session):
    response = client.post("/api/hprim/actes/ngap?patient_id=PAT-NGAP", json=_ngap_act_payload())
    assert response.status_code == 200
    body = response.json()
    acte_id = body["id"]

    stored = session.get(HprimNGAPAct, acte_id)
    assert stored is not None
    assert stored.patient_id == "PAT-NGAP"
    assert stored.lettre_cle == "AMI"

    get_response = client.get(f"/api/hprim/actes/ngap/{acte_id}")
    assert get_response.status_code == 200
    assert get_response.json()["nabms"] == [101, 202]

    update_payload = _ngap_act_payload(commentaire="ngap-updated")
    update_payload["coefficient"] = 3.0
    update_payload["nabms"] = [303]
    update_response = client.put(f"/api/hprim/actes/ngap/{acte_id}", json=update_payload)
    assert update_response.status_code == 200
    assert update_response.json()["coefficient"] == 3.0

    history_response = client.get("/api/hprim/actes/ngap/patient/PAT-NGAP/historique")
    assert history_response.status_code == 200
    history_body = history_response.json()
    assert history_body["total"] == 1
    assert history_body["actes"][0]["id"] == acte_id

    delete_response = client.delete(f"/api/hprim/actes/ngap/{acte_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"


def test_hprim_message_history_api_and_view(client: TestClient, session):
    emission_response = client.post("/api/hprim/actes/ngap/emission", json=_ngap_emission_payload())
    assert emission_response.status_code == 200
    message_id = emission_response.json()["message_id"]

    stored = session.get(HprimMessage, message_id)
    assert stored is not None
    assert stored.patient_id == "PAT-NGAP-EMIT"

    api_list = client.get("/api/hprim/messages", params={"patient_id": "PAT-NGAP-EMIT"})
    assert api_list.status_code == 200
    api_list_body = api_list.json()
    assert api_list_body["total"] >= 1
    assert any(item["message_id"] == message_id for item in api_list_body["items"])

    api_detail = client.get(f"/api/hprim/messages/{message_id}")
    assert api_detail.status_code == 200
    assert api_detail.json()["message_id"] == message_id

    history_view = client.get("/hprim/messages")
    assert history_view.status_code == 200
    assert "Historique HPRIM persistant" in history_view.text

    detail_view = client.get(f"/hprim/messages/{message_id}")
    assert detail_view.status_code == 200
    assert message_id in detail_view.text
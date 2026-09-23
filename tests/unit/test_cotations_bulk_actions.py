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


def test_rapid_entry_creates_and_rereads_every_cotation_type(client: TestClient, session: Session) -> None:
    """Le succès de la saisie rapide correspond à un acte réellement persisté.

    Les quatre formulaires de la page utilisent des routes distinctes. Ce test
    couvre leur contrat commun : création, identifiant retourné puis relecture
    par l'API du workspace et dans la base de données.
    """

    dossier = _dossier(session)
    execute_date = "2026-03-04T14:30:00"
    entries = [
        (
            "ccam",
            CCAMAct,
            {
                "dossier_id": dossier.id,
                "code_acte": "HBMD001",
                "code_activite": "01",
                "code_phase": "01",
                "execute_date": execute_date,
                "quantite": 2,
                "montant_total": 70.28,
                "commentaire": "Saisie rapide CCAM",
            },
            "code_acte",
            "HBMD001",
        ),
        (
            "ngap",
            NGAPAct,
            {
                "dossier_id": dossier.id,
                "lettre_cle": "AMI",
                "coefficient": 2,
                "denombrement": 3,
                "execute_date": execute_date,
                "montant_total": 21.0,
                "commentaire": "Saisie rapide NGAP",
            },
            "lettre_cle",
            "AMI",
        ),
        (
            "ucd",
            UCDAct,
            {
                "dossier_id": dossier.id,
                "code_ucd": "3400935001324",
                "denomination_libelle": "Produit UCD de test",
                "quantite": 2,
                "montant_unitaire_facture_ttc": 5.5,
                "execute_date": execute_date,
                "commentaire": "Saisie rapide UCD",
            },
            "code_ucd",
            "3400935001324",
        ),
        (
            "lpp",
            LPPAct,
            {
                "dossier_id": dossier.id,
                "code_lpp": "1234567890123",
                "denomination_libelle": "Dispositif LPP de test",
                "quantite": 1,
                "montant_unitaire_facture_ttc": 12.5,
                "execute_date": execute_date,
                "commentaire": "Saisie rapide LPP",
            },
            "code_lpp",
            "1234567890123",
        ),
    ]

    for acte_type, model, payload, code_field, expected_code in entries:
        created = client.post(f"/cotations/api/{acte_type}", json=payload)
        assert created.status_code == 200
        body = created.json()
        assert body["success"] is True
        acte_id = body["acte_id"]

        reread = client.get(f"/cotations/api/{acte_type}/{acte_id}")
        assert reread.status_code == 200
        assert reread.json()["type"] == acte_type
        assert reread.json()["id"] == acte_id
        assert reread.json()["commentaire"] == payload["commentaire"]

        session.expire_all()
        stored = session.get(model, acte_id)
        assert stored is not None
        assert stored.dossier_id == dossier.id
        assert getattr(stored, code_field) == expected_code


def test_cotation_common_fields_can_be_read_and_edited_for_every_type(client: TestClient, session: Session) -> None:
    """L'édition du workspace couvre les champs communs des quatre nomenclatures."""

    dossier = _dossier(session)
    initial_date = datetime(2026, 1, 2, 10, 0)
    edited_date = "2026-03-04T14:30:00"
    acts = [
        ("ccam", CCAMAct(dossier_id=dossier.id, code_acte="HBMD001", code_activite="01", code_phase="01", execute_date=initial_date), "quantite", "montant_total", 2, 15.5),
        ("ngap", NGAPAct(dossier_id=dossier.id, lettre_cle="AMI", coefficient=1, execute_date=initial_date), "denombrement", "montant_total", 3, 16.5),
        ("ucd", UCDAct(dossier_id=dossier.id, code_ucd="3400935001324", denomination_libelle="Produit UCD", quantite=1, execute_date=initial_date), "quantite", "montant_unitaire_facture_ttc", 1.5, 17.5),
        ("lpp", LPPAct(dossier_id=dossier.id, code_lpp="1234567890123", denomination_libelle="Produit LPP", montant_unitaire_facture_ttc=10, quantite=1, execute_date=initial_date), "quantite", "montant_unitaire_facture_ttc", 4, 18.5),
    ]
    for _, acte, *_ in acts:
        session.add(acte)
    session.commit()
    for _, acte, *_ in acts:
        session.refresh(acte)

    for acte_type, acte, quantity_field, amount_field, quantity, amount in acts:
        loaded = client.get(f"/cotations/api/{acte_type}/{acte.id}")
        assert loaded.status_code == 200
        assert loaded.json()["type"] == acte_type

        updated = client.patch(
            f"/cotations/api/{acte_type}/{acte.id}",
            json={
                "execute_date": edited_date,
                "quantity": quantity,
                "amount": amount,
                "commentaire": f"Correction {acte_type}",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["success"] is True

        session.expire_all()
        stored = session.get(type(acte), acte.id)
        assert stored is not None
        assert getattr(stored, quantity_field) == quantity
        assert getattr(stored, amount_field) == amount
        assert stored.commentaire == f"Correction {acte_type}"
        assert stored.execute_date.replace(tzinfo=None) == datetime.fromisoformat(edited_date)


def test_cotation_edit_rejects_fractional_quantity_for_integer_act(client: TestClient, session: Session) -> None:
    dossier = _dossier(session)
    acte = CCAMAct(dossier_id=dossier.id, code_acte="HBMD001", code_activite="01", code_phase="01", execute_date=datetime.now())
    session.add(acte)
    session.commit()
    session.refresh(acte)

    response = client.patch(f"/cotations/api/ccam/{acte.id}", json={"quantity": 1.5})
    assert response.status_code == 400
    assert "entier" in response.json()["detail"]

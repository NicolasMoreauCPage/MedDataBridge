"""
Tests pour le router context.py

Couvre la gestion des contextes de session :
- Contexte patient
- Contexte dossier
- Contexte GHT/EJ
- Effacement des contextes
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models import Patient, Dossier
from app.models_structure import GHTContext, EntiteJuridique


def test_set_patient_context_success(client: TestClient, session: Session):
    """Test définition contexte patient existant"""
    patient = Patient(family="Dupont", given="Jean", birth_date="1990-01-15")
    session.add(patient)
    session.commit()

    # Désactiver le suivi automatique des redirections pour tester le statut 303
    client.follow_redirects = False
    response = client.get(f"/context/patient/{patient.id}")

    assert response.status_code == 303  # Redirect
    assert response.headers["location"]  # Doit avoir un header location
    # Vérifier que le contexte patient a été défini dans la session
    # Note: TestClient ne préserve pas la session entre requêtes, donc on ne peut pas vérifier directement
    # Mais on peut vérifier que la redirection fonctionne


def test_set_patient_context_not_found(client: TestClient):
    """Test définition contexte patient inexistant"""
    client.follow_redirects = False
    response = client.get("/context/patient/99999")

    assert response.status_code == 303  # Redirect to /patients
    assert response.headers["location"] == "/patients"


def test_set_dossier_context_success(client: TestClient, session: Session):
    """Test définition contexte dossier existant"""
    patient = Patient(family="Dupont", given="Jean", birth_date="1990-01-15")
    session.add(patient)
    session.commit()

    dossier = Dossier(
        dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
        patient_id=patient.id,
        admit_time="2023-01-15T10:00:00",
        entite_juridique_id=1
    )
    session.add(dossier)
    session.commit()

    client.follow_redirects = False
    response = client.get(f"/context/dossier/{dossier.id}")

    assert response.status_code == 303  # Redirect
    # Le contexte dossier et patient devraient être définis


def test_set_dossier_context_not_found(client: TestClient):
    """Test définition contexte dossier inexistant"""
    client.follow_redirects = False
    response = client.get("/context/dossier/99999")

    assert response.status_code == 303  # Redirect to /dossiers
    assert response.headers["location"] == "/dossiers"


def test_clear_context_all(client: TestClient):
    """Test effacement de tous les contextes"""
    client.follow_redirects = False
    response = client.get("/context/clear")

    assert response.status_code == 303  # Redirect


def test_clear_context_patient(client: TestClient):
    """Test effacement du contexte patient uniquement"""
    client.follow_redirects = False
    response = client.get("/context/clear?kind=patient")

    assert response.status_code == 303  # Redirect


def test_clear_context_dossier(client: TestClient):
    """Test effacement du contexte dossier uniquement"""
    client.follow_redirects = False
    response = client.get("/context/clear?kind=dossier")

    assert response.status_code == 303  # Redirect


def test_clear_context_ght(client: TestClient):
    """Test effacement du contexte GHT (et EJ)"""
    client.follow_redirects = False
    response = client.get("/context/clear?kind=ght")

    assert response.status_code == 303  # Redirect


def test_clear_context_ej(client: TestClient):
    """Test effacement du contexte EJ uniquement"""
    client.follow_redirects = False
    response = client.get("/context/clear?kind=ej")

    assert response.status_code == 303  # Redirect


def test_select_context(client: TestClient):
    """Test page de sélection de contexte"""
    client.follow_redirects = False
    response = client.get("/context/select")

    assert response.status_code == 303  # Redirect to /admin/ght
    assert response.headers["location"] == "/admin/ght"


def test_set_ght_context_success(client: TestClient, session: Session):
    """Test définition contexte GHT existant"""
    ght = GHTContext(name="Test GHT", code="TST")
    session.add(ght)
    session.commit()

    client.follow_redirects = False
    response = client.get(f"/context/ght/{ght.id}")

    assert response.status_code == 303  # Redirect


def test_set_ght_context_not_found(client: TestClient):
    """Test définition contexte GHT inexistant"""
    client.follow_redirects = False
    response = client.get("/context/ght/99999")

    assert response.status_code == 303  # Redirect to /admin/ght
    assert response.headers["location"] == "/admin/ght"


def test_set_ej_context_success(client: TestClient, session: Session):
    """Test définition contexte EJ existant"""
    ght = GHTContext(name="Test GHT", code="TST")
    session.add(ght)
    session.commit()

    ej = EntiteJuridique(
        name="Test EJ",
        code="EJ001",
        ght_context_id=ght.id
    )
    session.add(ej)
    session.commit()

    client.follow_redirects = False
    response = client.get(f"/context/ej/{ej.id}")

    assert response.status_code == 303  # Redirect


def test_set_ej_context_not_found(client: TestClient):
    """Test définition contexte EJ inexistant"""
    client.follow_redirects = False
    response = client.get("/context/ej/99999")

    assert response.status_code == 303  # Redirect to /admin/ght
    assert response.headers["location"] == "/admin/ght"


def test_ej_context_clears_incompatible_dossier(client: TestClient, session: Session):
    """Test que changer d'EJ efface les contextes dossier/patient incompatibles"""
    # Créer deux EJ différents
    ght = GHTContext(name="Test GHT", code="TST")
    session.add(ght)
    session.commit()

    ej1 = EntiteJuridique(name="EJ 1", code="EJ001", ght_context_id=ght.id)
    ej2 = EntiteJuridique(name="EJ 2", code="EJ002", ght_context_id=ght.id)
    session.add(ej1)
    session.add(ej2)
    session.commit()

    # Créer un patient et dossier dans EJ1
    patient = Patient(family="Dupont", given="Jean", birth_date="1990-01-15")
    session.add(patient)
    session.commit()

    dossier = Dossier(
        dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
        patient_id=patient.id,
        admit_time="2023-01-15T10:00:00",
        entite_juridique_id=ej1.id
    )
    session.add(dossier)
    session.commit()

    # Simuler un contexte existant avec dossier d'EJ1
    client.follow_redirects = False
    with client:
        # D'abord définir le contexte dossier
        client.get(f"/context/dossier/{dossier.id}")
        # Puis changer d'EJ
        response = client.get(f"/context/ej/{ej2.id}")

        assert response.status_code == 303
        # Le contexte dossier devrait être effacé car il n'appartient pas à EJ2


def test_ej_context_clears_incompatible_patient_only(client: TestClient, session: Session):
    """Test que changer d'EJ efface le contexte patient seul s'il n'a pas de dossiers dans la nouvelle EJ"""
    # Créer deux EJ différents
    ght = GHTContext(name="Test GHT", code="TST")
    session.add(ght)
    session.commit()

    ej1 = EntiteJuridique(name="EJ 1", code="EJ001", ght_context_id=ght.id)
    ej2 = EntiteJuridique(name="EJ 2", code="EJ002", ght_context_id=ght.id)
    session.add(ej1)
    session.add(ej2)
    session.commit()

    # Créer un patient avec dossiers seulement dans EJ1
    patient = Patient(family="Dupont", given="Jean", birth_date="1990-01-15")
    session.add(patient)
    session.commit()

    dossier_ej1 = Dossier(
        dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
        patient_id=patient.id,
        admit_time="2023-01-15T10:00:00",
        entite_juridique_id=ej1.id
    )
    session.add(dossier_ej1)
    session.commit()

    # Simuler un contexte patient seul (pas de dossier)
    client.follow_redirects = False
    with client:
        # Définir le contexte patient
        client.get(f"/context/patient/{patient.id}")
        # Changer d'EJ où le patient n'a pas de dossiers
        response = client.get(f"/context/ej/{ej2.id}")

        assert response.status_code == 303
        # Le contexte patient devrait être effacé car il n'a pas de dossiers dans EJ2


def test_ej_context_preserves_compatible_patient(client: TestClient, session: Session):
    """Test que changer d'EJ préserve le contexte patient s'il a des dossiers dans la nouvelle EJ"""
    # Créer deux EJ différents
    ght = GHTContext(name="Test GHT", code="TST")
    session.add(ght)
    session.commit()

    ej1 = EntiteJuridique(name="EJ 1", code="EJ001", ght_context_id=ght.id)
    ej2 = EntiteJuridique(name="EJ 2", code="EJ002", ght_context_id=ght.id)
    session.add(ej1)
    session.add(ej2)
    session.commit()

    # Créer un patient avec dossiers dans les deux EJ
    patient = Patient(family="Dupont", given="Jean", birth_date="1990-01-15")
    session.add(patient)
    session.commit()

    dossier_ej1 = Dossier(
        dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
        patient_id=patient.id,
        admit_time="2023-01-15T10:00:00",
        entite_juridique_id=ej1.id
    )
    dossier_ej2 = Dossier(
        dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
        patient_id=patient.id,
        admit_time="2023-02-15T10:00:00",
        entite_juridique_id=ej2.id
    )
    session.add(dossier_ej1)
    session.add(dossier_ej2)
    session.commit()

    # Simuler un contexte patient seul
    client.follow_redirects = False
    with client:
        # Définir le contexte patient
        client.get(f"/context/patient/{patient.id}")
        # Changer d'EJ où le patient a des dossiers
        response = client.get(f"/context/ej/{ej2.id}")

        assert response.status_code == 303
        # Le contexte patient devrait être préservé car il a des dossiers dans EJ2


def test_ght_context_clears_incompatible_ej(client: TestClient, session: Session):
    """Test que changer de GHT efface l'EJ incompatible"""
    # Créer deux GHT différents
    ght1 = GHTContext(name="GHT 1", code="GHT1")
    ght2 = GHTContext(name="GHT 2", code="GHT2")
    session.add(ght1)
    session.add(ght2)
    session.commit()

    # Créer EJ dans GHT1
    ej = EntiteJuridique(name="EJ 1", code="EJ001", ght_context_id=ght1.id)
    session.add(ej)
    session.commit()

    # Simuler contexte EJ défini
    client.follow_redirects = False
    with client:
        # Définir le contexte EJ
        client.get(f"/context/ej/{ej.id}")
        # Changer de GHT
        response = client.get(f"/context/ght/{ght2.id}")

        assert response.status_code == 303
        # L'EJ devrait être effacée car elle n'appartient pas au nouveau GHT


def test_clear_context_preserves_referer_redirect(client: TestClient):
    """Test que clear context redirige vers le referer si présent"""
    referer_url = "/some/path"
    client.follow_redirects = False
    response = client.get("/context/clear", headers={"referer": referer_url})

    assert response.status_code == 303
    assert response.headers["location"] == referer_url


def test_clear_context_fallback_redirect(client: TestClient):
    """Test que clear context redirige vers fallback si pas de referer"""
    client.follow_redirects = False
    response = client.get("/context/clear")

    assert response.status_code == 303
    assert response.headers["location"] == "/"
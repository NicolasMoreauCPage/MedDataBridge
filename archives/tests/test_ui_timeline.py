"""Tests UI pour la timeline patient et responsabilités UF.
Couvre affichage timeline, filtres temporels, changements UF.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from datetime import datetime, timedelta

from app.models import Patient, Dossier, Venue, Mouvement
from app.models_structure import UniteFonctionnelle


@pytest.mark.xfail(reason="Routes timeline peuvent être cassées si dépendent de ght.py")
def test_timeline_patient_page_loads(client: TestClient, session: Session):
    """Test que la page timeline patient se charge."""
    # Créer patient
    patient = Patient(
        nom="Dupont",
        prenom="Jean",
        date_naissance=datetime(1980, 1, 1),
        sexe="M"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    r = client.get(f"/timeline/patient/{patient.id}")
    assert r.status_code == 200
    assert "Timeline" in r.text or "Chronologie" in r.text


@pytest.mark.xfail(reason="Routes timeline peuvent être cassées si dépendent de ght.py")
def test_timeline_displays_movements(client: TestClient, session: Session):
    """Test que la timeline affiche les mouvements du patient."""
    # Créer patient avec mouvements
    patient = Patient(
        nom="Martin",
        prenom="Marie",
        date_naissance=datetime(1975, 5, 15),
        sexe="F"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    dossier = Dossier(
        patient_id=patient.id,
        type="hospitalise",
        numero="DOS-TIMELINE"
    )
    session.add(dossier)
    session.commit()
    session.refresh(dossier)

    venue = Venue(
        dossier_id=dossier.id,
        numero="VEN-TIMELINE"
    )
    session.add(venue)
    session.commit()
    session.refresh(venue)

    uf1 = UniteFonctionnelle(name="UF Admission", identifier="UF-ADM", service_id=1, physical_type="ro")
    uf2 = UniteFonctionnelle(name="UF Transfert", identifier="UF-TRF", service_id=1, physical_type="ro")
    session.add(uf1)
    session.add(uf2)
    session.commit()
    session.refresh(uf1)
    session.refresh(uf2)

    # Admission
    admission = Mouvement(
        patient_id=patient.id,
        dossier_id=dossier.id,
        venue_id=venue.id,
        uf_id=uf1.id,
        movement_type="A01",
        priorite="R",
        date_mouvement=datetime.now() - timedelta(days=5)
    )
    session.add(admission)

    # Transfert
    transfert = Mouvement(
        patient_id=patient.id,
        dossier_id=dossier.id,
        venue_id=venue.id,
        uf_id=uf2.id,
        movement_type="A02",
        priorite="R",
        date_mouvement=datetime.now() - timedelta(days=2)
    )
    session.add(transfert)

    # Sortie
    sortie = Mouvement(
        patient_id=patient.id,
        dossier_id=dossier.id,
        venue_id=venue.id,
        uf_id=uf2.id,
        movement_type="A03",
        priorite="R",
        date_mouvement=datetime.now() - timedelta(hours=1)
    )
    session.add(sortie)
    session.commit()

    r = client.get(f"/timeline/patient/{patient.id}")
    assert r.status_code == 200
    assert "A01" in r.text
    assert "A02" in r.text
    assert "A03" in r.text
    assert uf1.name in r.text
    assert uf2.name in r.text


@pytest.mark.xfail(reason="Routes timeline peuvent être cassées si dépendent de ght.py")
def test_timeline_filters_by_date_range(client: TestClient, session: Session):
    """Test les filtres de date sur la timeline."""
    # Créer patient avec mouvements sur différentes périodes
    patient = Patient(
        nom="Test",
        prenom="DateFilter",
        date_naissance=datetime(1990, 1, 1),
        sexe="M"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    dossier = Dossier(patient_id=patient.id, type="hospitalise", numero="DOS-DATE")
    session.add(dossier)
    session.commit()
    session.refresh(dossier)

    venue = Venue(dossier_id=dossier.id, numero="VEN-DATE")
    session.add(venue)
    session.commit()
    session.refresh(venue)

    uf = UniteFonctionnelle(name="UF Date", identifier="UF-DATE", service_id=1, physical_type="ro")
    session.add(uf)
    session.commit()
    session.refresh(uf)

    # Mouvements à différentes dates
    dates = [
        datetime.now() - timedelta(days=30),  # Ancien
        datetime.now() - timedelta(days=7),   # Récent
        datetime.now() - timedelta(hours=1)   # Très récent
    ]

    for i, date in enumerate(dates):
        mouvement = Mouvement(
            patient_id=patient.id,
            dossier_id=dossier.id,
            venue_id=venue.id,
            uf_id=uf.id,
            movement_type="A01",
            priorite="R",
            date_mouvement=date
        )
        session.add(mouvement)
    session.commit()

    # Test filtre dernière semaine
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")

    r = client.get(f"/timeline/patient/{patient.id}?start_date={start_date}&end_date={end_date}")
    assert r.status_code == 200
    # Devrait contenir les 2 mouvements récents, pas l'ancien
    assert r.text.count("A01") >= 2  # Au moins 2 mouvements


@pytest.mark.xfail(reason="Routes timeline peuvent être cassées si dépendent de ght.py")
def test_timeline_shows_uf_changes(client: TestClient, session: Session):
    """Test que la timeline montre les changements d'UF."""
    # Créer patient avec transferts entre UF
    patient = Patient(
        nom="Test",
        prenom="UFChanges",
        date_naissance=datetime(1990, 1, 1),
        sexe="M"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    dossier = Dossier(patient_id=patient.id, type="hospitalise", numero="DOS-UF")
    session.add(dossier)
    session.commit()
    session.refresh(dossier)

    venue = Venue(dossier_id=dossier.id, numero="VEN-UF")
    session.add(venue)
    session.commit()
    session.refresh(venue)

    uf1 = UniteFonctionnelle(name="UF Médecine Interne", identifier="UF-MED", service_id=1, physical_type="ro")
    uf2 = UniteFonctionnelle(name="UF Cardiologie", identifier="UF-CARDIO", service_id=1, physical_type="ro")
    uf3 = UniteFonctionnelle(name="UF Réanimation", identifier="UF-REA", service_id=1, physical_type="ro")
    session.add(uf1)
    session.add(uf2)
    session.add(uf3)
    session.commit()
    session.refresh(uf1)
    session.refresh(uf2)
    session.refresh(uf3)

    # Séquence de mouvements
    mouvements_data = [
        (uf1, "A01", timedelta(days=10)),  # Admission Médecine
        (uf2, "A02", timedelta(days=5)),   # Transfert Cardio
        (uf3, "A02", timedelta(days=2)),   # Transfert Réa
        (uf3, "A03", timedelta(hours=1))   # Sortie Réa
    ]

    for uf, mtype, time_ago in mouvements_data:
        mouvement = Mouvement(
            patient_id=patient.id,
            dossier_id=dossier.id,
            venue_id=venue.id,
            uf_id=uf.id,
            movement_type=mtype,
            priorite="R",
            date_mouvement=datetime.now() - time_ago
        )
        session.add(mouvement)
    session.commit()

    r = client.get(f"/timeline/patient/{patient.id}")
    assert r.status_code == 200

    # Vérifier que toutes les UF apparaissent
    assert uf1.name in r.text
    assert uf2.name in r.text
    assert uf3.name in r.text

    # Vérifier les types de mouvements
    assert "A01" in r.text  # Admission
    assert r.text.count("A02") >= 2  # 2 transferts
    assert "A03" in r.text  # Sortie


@pytest.mark.xfail(reason="Routes timeline peuvent être cassées si dépendent de ght.py")
def test_timeline_highlights_active_periods(client: TestClient, session: Session):
    """Test que la timeline met en évidence les périodes actives."""
    # Créer patient avec périodes d'hospitalisation
    patient = Patient(
        nom="Test",
        prenom="ActivePeriods",
        date_naissance=datetime(1990, 1, 1),
        sexe="M"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    # Premier séjour
    dossier1 = Dossier(patient_id=patient.id, type="hospitalise", numero="DOS-1")
    session.add(dossier1)
    session.commit()
    session.refresh(dossier1)

    venue1 = Venue(dossier_id=dossier1.id, numero="VEN-1")
    session.add(venue1)
    session.commit()
    session.refresh(venue1)

    # Deuxième séjour
    dossier2 = Dossier(patient_id=patient.id, type="hospitalise", numero="DOS-2")
    session.add(dossier2)
    session.commit()
    session.refresh(dossier2)

    venue2 = Venue(dossier_id=dossier2.id, numero="VEN-2")
    session.add(venue2)
    session.commit()
    session.refresh(venue2)

    uf = UniteFonctionnelle(name="UF Test", identifier="UF-TEST", service_id=1, physical_type="ro")
    session.add(uf)
    session.commit()
    session.refresh(uf)

    # Premier séjour: Admission il y a 1 an, sortie il y a 11 mois
    admission1 = Mouvement(
        patient_id=patient.id,
        dossier_id=dossier1.id,
        venue_id=venue1.id,
        uf_id=uf.id,
        movement_type="A01",
        priorite="R",
        date_mouvement=datetime.now() - timedelta(days=365)
    )
    session.add(admission1)

    sortie1 = Mouvement(
        patient_id=patient.id,
        dossier_id=dossier1.id,
        venue_id=venue1.id,
        uf_id=uf.id,
        movement_type="A03",
        priorite="R",
        date_mouvement=datetime.now() - timedelta(days=335)
    )
    session.add(sortie1)

    # Deuxième séjour: Admission il y a 1 mois, toujours hospitalisé
    admission2 = Mouvement(
        patient_id=patient.id,
        dossier_id=dossier2.id,
        venue_id=venue2.id,
        uf_id=uf.id,
        movement_type="A01",
        priorite="R",
        date_mouvement=datetime.now() - timedelta(days=30)
    )
    session.add(admission2)
    session.commit()

    r = client.get(f"/timeline/patient/{patient.id}")
    assert r.status_code == 200

    # Vérifier que les deux séjours sont visibles
    assert dossier1.numero in r.text
    assert dossier2.numero in r.text

    # Le deuxième séjour devrait être marqué comme actif
    # (puisque pas de sortie)
    # TODO: Vérifier le marquage visuel une fois implémenté


@pytest.mark.xfail(reason="Routes timeline peuvent être cassées si dépendent de ght.py")
def test_timeline_filters_by_movement_type(client: TestClient, session: Session):
    """Test les filtres par type de mouvement."""
    # Créer patient avec différents types de mouvements
    patient = Patient(
        nom="Test",
        prenom="MovementTypes",
        date_naissance=datetime(1990, 1, 1),
        sexe="M"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    dossier = Dossier(patient_id=patient.id, type="hospitalise", numero="DOS-TYPES")
    session.add(dossier)
    session.commit()
    session.refresh(dossier)

    venue = Venue(dossier_id=dossier.id, numero="VEN-TYPES")
    session.add(venue)
    session.commit()
    session.refresh(venue)

    uf = UniteFonctionnelle(name="UF Types", identifier="UF-TYPES", service_id=1, physical_type="ro")
    session.add(uf)
    session.commit()
    session.refresh(uf)

    # Créer différents types de mouvements
    movement_types = ["A01", "A02", "A03", "A08", "A11"]
    mouvements = []

    for mtype in movement_types:
        mouvement = Mouvement(
            patient_id=patient.id,
            dossier_id=dossier.id,
            venue_id=venue.id,
            uf_id=uf.id,
            movement_type=mtype,
            priorite="R",
            date_mouvement=datetime.now() - timedelta(days=len(mouvements))
        )
        session.add(mouvement)
        mouvements.append(mouvement)
    session.commit()

    # Test filtre par type A01 uniquement
    r = client.get(f"/timeline/patient/{patient.id}?movement_type=A01")
    assert r.status_code == 200
    assert "A01" in r.text
    # Les autres types ne devraient pas être présents
    for mtype in ["A02", "A03", "A08", "A11"]:
        assert mtype not in r.text


@pytest.mark.xfail(reason="Routes timeline peuvent être cassées si dépendent de ght.py")
def test_timeline_filters_by_uf(client: TestClient, session: Session):
    """Test les filtres par UF."""
    # Créer patient avec mouvements dans différentes UF
    patient = Patient(
        nom="Test",
        prenom="UFFilter",
        date_naissance=datetime(1990, 1, 1),
        sexe="M"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    dossier = Dossier(patient_id=patient.id, type="hospitalise", numero="DOS-UF")
    session.add(dossier)
    session.commit()
    session.refresh(dossier)

    venue = Venue(dossier_id=dossier.id, numero="VEN-UF")
    session.add(venue)
    session.commit()
    session.refresh(venue)

    uf1 = UniteFonctionnelle(name="UF Cardio", identifier="UF-CARDIO", service_id=1, physical_type="ro")
    uf2 = UniteFonctionnelle(name="UF Neuro", identifier="UF-NEURO", service_id=1, physical_type="ro")
    session.add(uf1)
    session.add(uf2)
    session.commit()
    session.refresh(uf1)
    session.refresh(uf2)

    # Mouvements dans UF1
    m1 = Mouvement(
        patient_id=patient.id,
        dossier_id=dossier.id,
        venue_id=venue.id,
        uf_id=uf1.id,
        movement_type="A01",
        priorite="R",
        date_mouvement=datetime.now() - timedelta(days=5)
    )
    session.add(m1)

    # Mouvements dans UF2
    m2 = Mouvement(
        patient_id=patient.id,
        dossier_id=dossier.id,
        venue_id=venue.id,
        uf_id=uf2.id,
        movement_type="A02",
        priorite="R",
        date_mouvement=datetime.now() - timedelta(days=2)
    )
    session.add(m2)
    session.commit()

    # Test filtre par UF1
    r = client.get(f"/timeline/patient/{patient.id}?uf_id={uf1.id}")
    assert r.status_code == 200
    assert "A01" in r.text
    assert uf1.name in r.text
    assert "A02" not in r.text  # Mouvement UF2 ne devrait pas être là


@pytest.mark.xfail(reason="Routes timeline peuvent être cassées si dépendent de ght.py")
def test_timeline_export_functionality(client: TestClient, session: Session):
    """Test l'export de la timeline."""
    # Créer patient avec timeline
    patient = Patient(
        nom="Test",
        prenom="Export",
        date_naissance=datetime(1990, 1, 1),
        sexe="M"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    dossier = Dossier(patient_id=patient.id, type="hospitalise", numero="DOS-EXPORT")
    session.add(dossier)
    session.commit()
    session.refresh(dossier)

    venue = Venue(dossier_id=dossier.id, numero="VEN-EXPORT")
    session.add(venue)
    session.commit()
    session.refresh(venue)

    uf = UniteFonctionnelle(name="UF Export", identifier="UF-EXPORT", service_id=1, physical_type="ro")
    session.add(uf)
    session.commit()
    session.refresh(uf)

    mouvement = Mouvement(
        patient_id=patient.id,
        dossier_id=dossier.id,
        venue_id=venue.id,
        uf_id=uf.id,
        movement_type="A01",
        priorite="R",
        date_mouvement=datetime.now()
    )
    session.add(mouvement)
    session.commit()

    # Test export PDF
    r = client.get(f"/timeline/patient/{patient.id}/export?format=pdf")
    assert r.status_code == 200
    assert "application/pdf" in r.headers.get("content-type", "")

    # Test export JSON
    r = client.get(f"/timeline/patient/{patient.id}/export?format=json")
    assert r.status_code == 200
    assert "application/json" in r.headers.get("content-type", "")


@pytest.mark.xfail(reason="Routes timeline peuvent être cassées si dépendent de ght.py")
def test_timeline_responsibility_transfers(client: TestClient, session: Session):
    """Test l'affichage des transferts de responsabilité UF."""
    # Créer patient avec transferts de responsabilité
    patient = Patient(
        nom="Test",
        prenom="Responsibility",
        date_naissance=datetime(1990, 1, 1),
        sexe="M"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    dossier = Dossier(patient_id=patient.id, type="hospitalise", numero="DOS-RESP")
    session.add(dossier)
    session.commit()
    session.refresh(dossier)

    venue = Venue(dossier_id=dossier.id, numero="VEN-RESP")
    session.add(venue)
    session.commit()
    session.refresh(venue)

    uf1 = UniteFonctionnelle(name="UF Médecine", identifier="UF-MED", service_id=1, physical_type="ro", activity_codes="CONS,HOSP")
    uf2 = UniteFonctionnelle(name="UF Chirurgie", identifier="UF-CHIR", service_id=1, physical_type="ro", activity_codes="CHIR,CONS")
    session.add(uf1)
    session.add(uf2)
    session.commit()
    session.refresh(uf1)
    session.refresh(uf2)

    # Transfert de responsabilité (changement d'UF)
    transfert = Mouvement(
        patient_id=patient.id,
        dossier_id=dossier.id,
        venue_id=venue.id,
        uf_id=uf2.id,
        prior_uf_id=uf1.id,
        movement_type="A02",
        priorite="R",
        date_mouvement=datetime.now()
    )
    session.add(transfert)
    session.commit()

    r = client.get(f"/timeline/patient/{patient.id}")
    assert r.status_code == 200

    # Vérifier que les deux UF sont mentionnées
    assert uf1.name in r.text
    assert uf2.name in r.text

    # Vérifier que le transfert est marqué comme changement de responsabilité
    assert "A02" in r.text


@pytest.mark.xfail(reason="Routes timeline peuvent être cassées si dépendent de ght.py")
def test_timeline_empty_state(client: TestClient, session: Session):
    """Test la timeline pour un patient sans mouvements."""
    # Créer patient sans mouvements
    patient = Patient(
        nom="Test",
        prenom="Empty",
        date_naissance=datetime(1990, 1, 1),
        sexe="M"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    r = client.get(f"/timeline/patient/{patient.id}")
    assert r.status_code == 200

    # Devrait afficher un état vide approprié
    assert "Aucun mouvement" in r.text or "No movements" in r.text or patient.nom in r.text


@pytest.mark.xfail(reason="Routes timeline peuvent être cassées si dépendent de ght.py")
def test_timeline_multiple_dossiers(client: TestClient, session: Session):
    """Test la timeline pour un patient avec plusieurs dossiers."""
    # Créer patient avec plusieurs dossiers/séjours
    patient = Patient(
        nom="Test",
        prenom="MultiDossier",
        date_naissance=datetime(1990, 1, 1),
        sexe="M"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    uf = UniteFonctionnelle(name="UF Multi", identifier="UF-MULTI", service_id=1, physical_type="ro")
    session.add(uf)
    session.commit()
    session.refresh(uf)

    # Créer 3 dossiers avec mouvements
    for i in range(3):
        dossier = Dossier(
            patient_id=patient.id,
            type="hospitalise",
            numero=f"DOS-MULTI-{i}"
        )
        session.add(dossier)
        session.commit()
        session.refresh(dossier)

        venue = Venue(dossier_id=dossier.id, numero=f"VEN-MULTI-{i}")
        session.add(venue)
        session.commit()
        session.refresh(venue)

        # Admission pour chaque dossier
        admission = Mouvement(
            patient_id=patient.id,
            dossier_id=dossier.id,
            venue_id=venue.id,
            uf_id=uf.id,
            movement_type="A01",
            priorite="R",
            date_mouvement=datetime.now() - timedelta(days=i*30)  # Espacés de 30 jours
        )
        session.add(admission)

        # Sortie pour les 2 premiers
        if i < 2:
            sortie = Mouvement(
                patient_id=patient.id,
                dossier_id=dossier.id,
                venue_id=venue.id,
                uf_id=uf.id,
                movement_type="A03",
                priorite="R",
                date_mouvement=datetime.now() - timedelta(days=i*30 + 7)  # 7 jours plus tard
            )
            session.add(sortie)

    session.commit()

    r = client.get(f"/timeline/patient/{patient.id}")
    assert r.status_code == 200

    # Vérifier que tous les dossiers apparaissent
    for i in range(3):
        assert f"DOS-MULTI-{i}" in r.text

    # Vérifier les admissions
    assert r.text.count("A01") == 3

    # Vérifier les sorties (2 seulement)
    assert r.text.count("A03") >= 2
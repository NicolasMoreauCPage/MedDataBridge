"""
Tests pour vérifier l'indépendance des ScenarioTemplate capturés.

Principe :
1. Créer un Dossier avec Venues et Mouvements
2. Capturer comme ScenarioTemplate
3. Modifier/Supprimer le Dossier source
4. Vérifier que le ScenarioTemplate reste intact (snapshot indépendant)
"""
import pytest
from datetime import datetime, timedelta
from sqlmodel import Session, create_engine, select
from app.models_scenarios import ScenarioTemplate, ScenarioTemplateStep
from app.models import Dossier, Venue, Mouvement, Patient
from app.models_structure_fhir import EntiteJuridique
from app.services.scenario_capture import capture_dossier_as_template


@pytest.fixture
def test_session():
    """Session de test en mémoire (isolée)."""
    engine = create_engine("sqlite:///:memory:")
    from app.models import SQLModel
    from app.models_structure_fhir import GHTContext
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # Créer contexte GHT minimal
        ght_ctx = GHTContext(name="GHT Test")
        session.add(ght_ctx)
        session.commit()
        session.refresh(ght_ctx)
        
        ej = EntiteJuridique(
            name="EJ Test",
            finess_ej="TEST",
            ght_context_id=ght_ctx.id,
        )
        session.add(ej)
        session.commit()
        
        yield session


def test_template_independence_after_dossier_modification(test_session: Session):
    """
    Test 1 : Modification du dossier source ne doit pas affecter le template.
    """
    # 1. Créer patient + dossier + venue + mouvement
    patient = Patient(
        family="Doe",
        given="John",
        birth_date=datetime(1980, 1, 1),
        gender="M",
    )
    test_session.add(patient)
    test_session.commit()
    
    dossier = Dossier(
        patient_id=patient.id,
        numero_dossier="DOS-001",
        uf_responsabilite="URG",
        admission_type="emergency",
        admit_time=datetime.now(),
    )
    test_session.add(dossier)
    test_session.commit()
    
    venue = Venue(
        dossier_id=dossier.id,
        venue_seq=1,
        service_code="URG",
        uf_responsabilite="URG",
        start_time=datetime.now(),
        statut="EN_COURS",
    )
    test_session.add(venue)
    test_session.commit()
    
    mvt = Mouvement(
        venue_id=venue.id,
        mouvement_seq=1,
        type_mouvement="ENTREE",
        date_heure_mouvement=datetime.now(),
    )
    test_session.add(mvt)
    test_session.commit()
    
    # 2. Capturer comme template
    template = capture_dossier_as_template(
        db=test_session,
        dossier_id=dossier.id,
        template_name="Template Test Indépendance",
    )
    
    # Vérifier template créé avec 1 step
    assert template.id is not None
    assert template.name == "Template Test Indépendance"
    assert len(template.steps) == 1
    original_step_narrative = template.steps[0].narrative
    
    # 3. MODIFIER le dossier source (changer UF, admission_type)
    dossier.uf_responsabilite = "CHIRURGIE_MODIFIEE"
    dossier.admission_type = "elective_modifiee"
    test_session.add(dossier)
    test_session.commit()
    
    # 4. Recharger le template depuis la DB et vérifier qu'il est INTACT
    test_session.refresh(template)
    assert len(template.steps) == 1
    assert template.steps[0].narrative == original_step_narrative
    # Le template doit toujours référencer "URG" (snapshot au moment de la capture)
    assert "URG" in template.steps[0].reference_payload_hl7 or "URG" in template.steps[0].narrative
    assert "CHIRURGIE_MODIFIEE" not in template.steps[0].narrative


def test_template_independence_after_dossier_deletion(test_session: Session):
    """
    Test 2 : Suppression du dossier source ne doit pas affecter le template.
    """
    # 1. Créer patient + dossier + venue + mouvement
    patient = Patient(
        family="Smith",
        given="Jane",
        birth_date=datetime(1990, 5, 15),
        gender="F",
    )
    test_session.add(patient)
    test_session.commit()
    
    dossier = Dossier(
        patient_id=patient.id,
        numero_dossier="DOS-002",
        uf_responsabilite="MEDECINE",
        admission_type="emergency",
        admit_time=datetime.now(),
    )
    test_session.add(dossier)
    test_session.commit()
    
    venue = Venue(
        dossier_id=dossier.id,
        venue_seq=1,
        service_code="MED",
        uf_responsabilite="MEDECINE",
        start_time=datetime.now(),
        statut="EN_COURS",
    )
    test_session.add(venue)
    test_session.commit()
    
    mvt1 = Mouvement(
        venue_id=venue.id,
        mouvement_seq=1,
        type_mouvement="ENTREE",
        date_heure_mouvement=datetime.now(),
    )
    mvt2 = Mouvement(
        venue_id=venue.id,
        mouvement_seq=2,
        type_mouvement="SORTIE",
        date_heure_mouvement=datetime.now() + timedelta(hours=2),
    )
    test_session.add_all([mvt1, mvt2])
    test_session.commit()
    
    # 2. Capturer comme template
    template = capture_dossier_as_template(
        db=test_session,
        dossier_id=dossier.id,
        template_name="Template Test Suppression",
    )
    
    # Vérifier 2 steps
    assert len(template.steps) == 2
    step1_narrative = template.steps[0].narrative
    step2_narrative = template.steps[1].narrative
    
    # 3. SUPPRIMER le dossier source (cascade devrait supprimer venues et mouvements)
    dossier_id = dossier.id
    test_session.delete(dossier)
    test_session.commit()
    
    # Vérifier dossier supprimé
    deleted_dossier = test_session.get(Dossier, dossier_id)
    assert deleted_dossier is None
    
    # 4. Recharger le template depuis la DB et vérifier qu'il est INTACT
    test_session.refresh(template)
    assert len(template.steps) == 2
    assert template.steps[0].narrative == step1_narrative
    assert template.steps[1].narrative == step2_narrative
    # Le template doit contenir les données snapshot (pas de FK cassée)
    assert "ENTREE" in template.steps[0].narrative
    assert "SORTIE" in template.steps[1].narrative


def test_template_no_foreign_key_to_dossier(test_session: Session):
    """
    Test 3 : Vérifier que ScenarioTemplate n'a PAS de FK vers Dossier.
    """
    # Créer patient + dossier minimal
    patient = Patient(
        family="Test",
        given="NoFK",
        birth_date=datetime(1985, 10, 20),
        gender="M",
    )
    test_session.add(patient)
    test_session.commit()
    
    dossier = Dossier(
        patient_id=patient.id,
        numero_dossier="DOS-003",
        uf_responsabilite="TEST",
        admit_time=datetime.now(),
    )
    test_session.add(dossier)
    test_session.commit()
    
    venue = Venue(
        dossier_id=dossier.id,
        venue_seq=1,
        service_code="TEST",
        start_time=datetime.now(),
        statut="EN_COURS",
    )
    test_session.add(venue)
    test_session.commit()
    
    mvt = Mouvement(
        venue_id=venue.id,
        mouvement_seq=1,
        type_mouvement="ENTREE",
        date_heure_mouvement=datetime.now(),
    )
    test_session.add(mvt)
    test_session.commit()
    
    # Capturer
    template = capture_dossier_as_template(
        db=test_session,
        dossier_id=dossier.id,
    )
    
    # Vérifier qu'il n'y a PAS de colonne dossier_id dans ScenarioTemplate
    assert not hasattr(template, "dossier_id")
    # Vérifier que les steps n'ont PAS de FK vers Mouvement/Venue
    for step in template.steps:
        assert not hasattr(step, "mouvement_id")
        assert not hasattr(step, "venue_id")

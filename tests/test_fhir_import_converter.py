"""
Tests pour les convertisseurs FHIR → Models (import).
"""
import pytest
from datetime import datetime
from sqlmodel import Session, create_engine, SQLModel
from sqlalchemy.pool import StaticPool

from app.models_structure_fhir import GHTContext, EntiteJuridique
from app.models_structure import (
    EntiteGeographique, Pole, Service, UniteFonctionnelle,
    UniteHebergement, Chambre, Lit, LocationPhysicalType
)
from app.models import Patient, Dossier
from app.converters.fhir_import_converter import (
    FHIRToLocationConverter,
    FHIRToPatientConverter,
    FHIRToEncounterConverter,
    FHIRBundleImporter,
    FHIRImportError
)


@pytest.fixture
def session():
    """Session de test en mémoire."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # Créer le contexte de test
        ght = GHTContext(name="GHT Test", code="TEST001")
        session.add(ght)
        session.commit()
        session.refresh(ght)
        
        ej = EntiteJuridique(
            name="EJ Test",
            finess_ej="EJ001",
            ght_context_id=ght.id
        )
        session.add(ej)
        session.commit()
        session.refresh(ej)
        
        yield session


def test_import_location_eg(session):
    """Test l'import d'une Location FHIR vers EntiteGeographique."""
    ej = session.query(EntiteJuridique).first()
    
    fhir_location = {
        "resourceType": "Location",
        "identifier": [
            {"system": "http://example.org/eg", "value": "EG001"}
        ],
        "name": "Site Principal",
        "description": "Site principal de l'hôpital",
        "physicalType": {
            "coding": [
                {"code": "si", "system": "http://terminology.hl7.org/CodeSystem/location-physical-type"}
            ]
        }
    }
    
    converter = FHIRToLocationConverter(session, ej)
    eg = converter.convert_location(fhir_location)
    
    assert eg is not None
    assert isinstance(eg, EntiteGeographique)
    assert eg.name == "Site Principal"
    assert eg.identifier == "EG001"
    assert eg.description == "Site principal de l'hôpital"
    assert eg.entite_juridique_id == ej.id


def test_import_location_chambre(session):
    """Test l'import d'une Location FHIR vers Chambre."""
    ej = session.query(EntiteJuridique).first()
    
    # Créer la hiérarchie nécessaire avec identifier (NOT NULL)
    eg = EntiteGeographique(
        name="Site",
        identifier="EG-TEST-001",
        finess="999999999",
        entite_juridique_id=ej.id
    )
    session.add(eg)
    session.commit()
    session.refresh(eg)
    
    pole = Pole(
        name="Pole",
        identifier="POLE-001",
        entite_geo_id=eg.id,
        physical_type="bu"
    )
    session.add(pole)
    session.commit()
    session.refresh(pole)
    
    service = Service(
        name="Service",
        identifier="SERV-001",
        pole_id=pole.id,
        physical_type="wi",
        service_type="MCO"
    )
    session.add(service)
    session.commit()
    session.refresh(service)
    
    uf = UniteFonctionnelle(
        name="UF",
        identifier="UF-001",
        service_id=service.id,
        physical_type="wa"
    )
    session.add(uf)
    session.commit()
    session.refresh(uf)
    
    uh = UniteHebergement(
        name="UH",
        identifier="UH-001",
        unite_fonctionnelle_id=uf.id,
        physical_type="lv"
    )
    session.add(uh)
    session.commit()
    session.refresh(uh)
    
    fhir_location = {
        "resourceType": "Location",
        "identifier": [
            {"system": "http://example.org/chambre", "value": "CH101"}
        ],
        "name": "Chambre 101",
        "physicalType": {
            "coding": [
                {"code": "ro", "system": "http://terminology.hl7.org/CodeSystem/location-physical-type"}
            ]
        },
        "partOf": {
            "reference": f"Location/{uh.id}"
        }
    }
    
    converter = FHIRToLocationConverter(session, ej)
    chambre = converter.convert_location(fhir_location)
    
    assert chambre is not None
    assert isinstance(chambre, Chambre)
    assert chambre.name == "Chambre 101"
    assert chambre.identifier == "CH101"
    assert chambre.unite_hebergement_id == uh.id


def test_import_patient(session):
    """Test l'import d'un Patient FHIR."""
    ej = session.query(EntiteJuridique).first()
    
    fhir_patient = {
        "resourceType": "Patient",
        "identifier": [
            {"system": "http://example.org/ipp", "value": "IPP123456"}
        ],
        "name": [
            {
                "use": "official",
                "family": "Dupont",
                "given": ["Jean", "Pierre"]
            }
        ],
        "gender": "male",
        "birthDate": "1980-01-15"
    }
    
    converter = FHIRToPatientConverter(session, ej)
    patient = converter.convert_patient(fhir_patient)
    
    assert patient is not None
    assert patient.nom == "Dupont"
    assert patient.prenom == "Jean Pierre"
    assert patient.sexe == "M"
    assert patient.date_naissance.year == 1980
    assert patient.date_naissance.month == 1
    assert patient.date_naissance.day == 15
    
    # Vérifier qu'un dossier a été créé
    dossier = session.query(Dossier).filter(Dossier.patient_id == patient.id).first()
    assert dossier is not None
    assert dossier.ej_id == ej.id


def test_import_encounter(session):
    """Test l'import d'un Encounter FHIR."""
    ej = session.query(EntiteJuridique).first()
    
    # Créer un patient et un dossier
    patient = Patient(
        nom="Martin",
        prenom="Sophie",
        date_naissance=datetime(1990, 5, 10),
        sexe="F"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)
    
    dossier = Dossier(
        patient_id=patient.id,
        ej_id=ej.id,
        date_ouverture=datetime.now()
    )
    session.add(dossier)
    session.commit()
    
    fhir_encounter = {
        "resourceType": "Encounter",
        "identifier": [
            {"system": "http://example.org/nda", "value": "NDA7890"}
        ],
        "status": "in-progress",
        "class": {
            "code": "IMP",
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode"
        },
        "subject": {
            "reference": f"Patient/{patient.id}"
        },
        "period": {
            "start": "2025-01-01T10:00:00Z",
            "end": "2025-01-05T16:00:00Z"
        }
    }
    
    converter = FHIRToEncounterConverter(session)
    mouvement = converter.convert_encounter(fhir_encounter)
    
    assert mouvement is not None
    assert mouvement.dossier_id == dossier.id
    assert mouvement.type == "IMP"
    assert mouvement.statut == "EN_COURS"
    assert mouvement.date_debut is not None
    assert mouvement.date_fin is not None


def test_import_bundle_complet(session):
    """Test l'import d'un bundle FHIR complet."""
    ej = session.query(EntiteJuridique).first()
    
    # Créer un patient et un dossier pour le test encounter
    patient = Patient(
        nom="Test",
        prenom="Patient",
        date_naissance=datetime(1985, 3, 20),
        sexe="M"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)
    
    dossier = Dossier(
        patient_id=patient.id,
        ej_id=ej.id,
        date_ouverture=datetime.now()
    )
    session.add(dossier)
    session.commit()
    
    bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {
                "resource": {
                    "resourceType": "Location",
                    "identifier": [{"system": "http://example.org/eg", "value": "EG002"}],
                    "name": "Nouveau Site",
                    "physicalType": {
                        "coding": [{"code": "si"}]
                    }
                }
            },
            {
                "resource": {
                    "resourceType": "Patient",
                    "identifier": [{"system": "http://example.org/ipp", "value": "IPP999"}],
                    "name": [{"use": "official", "family": "Nouveau", "given": ["Patient"]}],
                    "gender": "female",
                    "birthDate": "1995-06-25"
                }
            },
            {
                "resource": {
                    "resourceType": "Encounter",
                    "identifier": [{"system": "http://example.org/nda", "value": "NDA999"}],
                    "status": "planned",
                    "class": {"code": "AMB"},
                    "subject": {"reference": f"Patient/{patient.id}"},
                    "period": {"start": "2025-02-01T09:00:00Z"}
                }
            }
        ]
    }
    
    importer = FHIRBundleImporter(session, ej)
    result = importer.import_bundle(bundle)
    
    assert result["total"] == 3
    assert result["imported"] == 3
    assert result["locations"] == 1
    assert result["patients"] == 1
    assert result["encounters"] == 1
    assert len(result["errors"]) == 0


def test_import_bundle_avec_erreurs(session):
    """Test l'import d'un bundle avec des ressources invalides."""
    ej = session.query(EntiteJuridique).first()
    
    bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {
                "resource": {
                    "resourceType": "Location",
                    "identifier": [{"system": "http://example.org/eg", "value": "EG003"}],
                    "name": "Site Valide",
                    "physicalType": {"coding": [{"code": "si"}]}
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",  # Type non supporté
                    "identifier": [{"value": "OBS001"}]
                }
            }
        ]
    }
    
    importer = FHIRBundleImporter(session, ej)
    result = importer.import_bundle(bundle)
    
    assert result["total"] == 2
    assert result["imported"] >= 1  # Au moins la location valide
    # Le type non supporté ne génère pas d'erreur, il est juste ignoré


def test_import_patient_sans_nom(session):
    """Test l'import d'un patient sans nom (devrait gérer gracieusement)."""
    ej = session.query(EntiteJuridique).first()
    
    fhir_patient = {
        "resourceType": "Patient",
        "identifier": [
            {"system": "http://example.org/ipp", "value": "IPP_NO_NAME"}
        ],
        "gender": "unknown"
    }
    
    converter = FHIRToPatientConverter(session, ej)
    patient = converter.convert_patient(fhir_patient)
    
    assert patient is not None
    assert patient.nom == ""  # Nom vide
    assert patient.sexe == "I"  # Inconnu


def test_import_location_type_invalide(session):
    """Test l'import d'une location avec un type physique invalide."""
    ej = session.query(EntiteJuridique).first()
    
    fhir_location = {
        "resourceType": "Location",
        "name": "Location Invalide",
        "physicalType": {
            "coding": [{"code": "invalid_type"}]
        }
    }
    
    converter = FHIRToLocationConverter(session, ej)
    
    with pytest.raises(FHIRImportError):
        converter.convert_location(fhir_location)

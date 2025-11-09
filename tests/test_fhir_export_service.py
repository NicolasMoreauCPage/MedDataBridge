"""Tests du service d'export FHIR."""
import pytest
from datetime import datetime
from sqlmodel import Session, SQLModel, create_engine
from app.models_structure_fhir import GHTContext, EntiteJuridique, EntiteGeographique
from app.models_structure import (
    Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit
)
from app.models import Patient, Dossier, Venue, Mouvement, Sequence
from app.models_identifiers import Identifier, IdentifierType
from app.services.fhir_export_service import FHIRExportService

# Base de test SQLite en mémoire
@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        # Initialize sequences
        sequences = {
            "venue": 1,
            "patient": 1,
            "dossier": 1,
            "mouvement": 1,
            "identifier": 1
        }
        for name, value in sequences.items():
            session.add(Sequence(name=name, value=value))
        session.commit()
        yield session

# Données de test
@pytest.fixture(name="test_data")
def test_data_fixture(session: Session):
    # GHT
    ght = GHTContext(
        name="GHT Test",
        code="GHT-TEST",
        oid_racine="1.2.3",
        fhir_server_url="http://test.com/fhir",
        is_active=True
    )
    session.add(ght)
    
    session.commit()
    session.refresh(ght)

    # EJ
    ej = EntiteJuridique(
        name="Hôpital Test",
        finess_ej="123456789",
        ght_context_id=ght.id,
        is_active=True
    )
    session.add(ej)
    session.commit()
    session.refresh(ej)
    
    # EG
    eg = EntiteGeographique(
        identifier="EG1",
        name="Site Principal",
        entite_juridique_id=ej.id,
        finess="123456789",
        is_active=True
    )
    session.add(eg)
    session.commit()
    session.refresh(eg)
    
    # Pôle
    pole = Pole(
        identifier="P1",
        name="Pôle Médecine",
        entite_geo_id=eg.id,
        physical_type="SI"
    )
    session.add(pole)
    session.commit()
    session.refresh(pole)
    
    # Service
    service = Service(
        identifier="S1",
        name="Cardiologie",
        pole_id=pole.id,
        physical_type="SI",
        service_type="MCO"
    )
    session.add(service)
    session.commit()
    session.refresh(service)
    
    # UF
    uf = UniteFonctionnelle(
        identifier="UF1",
        name="UF Cardio",
        service_id=service.id,
        physical_type="SI"
    )
    session.add(uf)
    session.commit()
    session.refresh(uf)
    
    # UH
    uh = UniteHebergement(
        identifier="UH1",
        name="UH Cardio",
        unite_fonctionnelle_id=uf.id,
        physical_type="WI"
    )
    session.add(uh)
    session.commit()
    session.refresh(uh)
    
    # Chambre
    chambre = Chambre(
        identifier="CH1",
        name="Chambre 101",
        unite_hebergement_id=uh.id,
        physical_type="RO"
    )
    session.add(chambre)
    session.commit()
    session.refresh(chambre)
    
    # Lit
    lit = Lit(
        identifier="L1",
        name="Lit A",
        chambre_id=chambre.id,
        physical_type="bd"  # Must match the LocationPhysicalType enum value
    )
    session.add(lit)
    session.commit()
    session.refresh(lit)
    
        # Patient
    patient = Patient(
        identifier="P123",
        family="DOE",
        given="John"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    # Dossier 
    dossier = Dossier(
        dossier_seq=1,
        patient_id=patient.id,
        admit_time=datetime.now()
    )
    session.add(dossier)
    session.commit()
    session.refresh(dossier)

    # Venue
    venue = Venue(
        venue_seq=1,
        dossier_id=dossier.id,
        uf_responsabilite=uf.identifier,  # Link to UF by its identifier
        start_time=datetime.now()
    )
    session.add(venue)
    session.commit()
    session.refresh(venue)
    
    # Add identifier for venue
    venue_id = Identifier(
        value="V123",
        type=IdentifierType.NDA,
        system="urn:oid:1.2.3.4.5",
        venue_id=venue.id
    )
    session.add(venue_id)
    session.commit()

    # Mouvements
    now = datetime.now()
    mvt1 = Mouvement(
        mouvement_seq=1,  # Required field
        venue_id=venue.id,
        when=now,  # Required field
        action_code="ADMIT",
        action="INSERT"
    )
    session.add(mvt1)

    session.commit()
    session.refresh(ej)
    return ej

def test_structure_export(session: Session, test_data: EntiteJuridique):
    """Test l'export de la structure."""
    service = FHIRExportService(session, "http://test.com/fhir")
    
    # Export
    bundle = service.export_structure(test_data)
    
    # Vérifications
    assert bundle.type == "transaction"
    assert len(bundle.entry) == 7  # EG + Pôle + Service + UF + UH + Chambre + Lit
    
    # Vérifier la première entrée (EG)
    first_entry = bundle.entry[0]
    location = first_entry["resource"]
    assert location["resourceType"] == "Location"
    assert location["identifier"][0]["value"] == "EG1"
    assert location["name"] == "Site Principal"
    assert location["type"][0]["coding"][0]["code"] == "ETBL"
    
    # Vérifier le lit
    last_entry = bundle.entry[-1]
    location = last_entry["resource"]
    assert location["resourceType"] == "Location"
    assert location["identifier"][0]["value"] == "L1"
    assert location["name"] == "Lit A"
    assert location["physicalType"]["coding"][0]["code"] == "bd"
    assert "partOf" in location

def test_patient_export(session: Session, test_data: EntiteJuridique):
    """Test l'export des patients."""
    service = FHIRExportService(session, "http://test.com/fhir")
    
    # Export
    bundle = service.export_patients(test_data)
    
    # Vérifications
    assert len(bundle.entry) == 1
    
    patient = bundle.entry[0]["resource"]
    assert patient["resourceType"] == "Patient"
    assert patient["identifier"][0]["value"] == "P123"
    assert patient["name"][0]["family"] == "DOE"
    assert patient["name"][0]["given"] == ["John"]
    assert "managingOrganization" in patient

def test_venue_export(session: Session, test_data: EntiteJuridique):
    """Test l'export des venues."""
    service = FHIRExportService(session, "http://test.com/fhir")
    
    # Export structure d'abord pour avoir les références
    service.export_structure(test_data)
    
    # Export patients pour avoir les références
    service.export_patients(test_data)
    
    # Export venues
    bundle = service.export_venues(test_data)
    
    # Vérifications
    assert len(bundle.entry) == 1
    
    encounter = bundle.entry[0]["resource"]
    assert encounter["resourceType"] == "Encounter"
    assert encounter["identifier"][0]["value"] == "V123"
    assert encounter["status"] == "in-progress"
    assert "subject" in encounter
    assert "location" in encounter
    assert "period" in encounter
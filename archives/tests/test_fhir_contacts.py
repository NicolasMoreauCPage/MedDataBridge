"""Tests basiques pour l'export FHIR des contacts PatientContact et VenueContact.

Vérifie que:
- Patient.contact[] est généré avec relationship coding HL7 v2-0063
- RelatedPerson ressources créées pour VenueContact
- Encounter.participant référence les RelatedPerson
"""
from sqlmodel import Session, create_engine
from datetime import datetime, date

from app.models import Patient, Dossier, Venue, Mouvement
from app.vocabulary_init import init_vocabularies
from app.models_contacts import PatientContact, VenueContact
from app.db import get_next_sequence
from app.services.fhir_export_service import FHIRExportService
from app.models_structure import EntiteJuridique, EntiteGeographique
from app.models_structure import Pole, Service, UniteFonctionnelle

def setup_in_memory_db():
    # Utilise SQLite mémoire pour test isolé
    engine = create_engine("sqlite:///:memory:")
    from sqlmodel import SQLModel
    from app.models_vocabulary import VocabularySystem, VocabularyValue
    SQLModel.metadata.create_all(engine)
    return Session(engine)

def create_minimal_structure(session: Session):
    # Patch: ght_context_id is required (NOT NULL)
    ej = EntiteJuridique(name="EJ Test", finess_ej="123456789", ght_context_id=1)
    session.add(ej); session.flush()
    eg = EntiteGeographique(name="EG Test", identifier="EG1", finess="987654321", entite_juridique_id=ej.id)
    session.add(eg); session.flush()
    pole = Pole(identifier="P1", name="Pole Test", entite_geo_id=eg.id, physical_type="SI")
    session.add(pole); session.flush()
    service = Service(identifier="S1", name="Service Test", pole_id=pole.id, physical_type="SI", service_type="TEST")
    session.add(service); session.flush()
    uf = UniteFonctionnelle(identifier="UF1", name="UF Test", service_id=service.id, physical_type="SI")
    session.add(uf); session.flush()
    return ej

def create_patient_with_contacts(session: Session):
    p = Patient(patient_seq=1, identifier="PAT1", external_id="PAT1", family="Doe", given="John", gender="male")
    session.add(p); session.flush()
    # Contacts patient
    c1 = PatientContact(patient_id=p.id, sequence=1, family_name="Doe", given_name="Jane", relationship_code="SPO", relationship_display="Conjoint", phone_number="+3312345678")
    c2 = PatientContact(patient_id=p.id, sequence=2, family_name="Doe", given_name="Emily", relationship_code="CHD", relationship_display="Enfant", phone_number="+339999999")
    session.add(c1); session.add(c2); session.flush()
    # Dossier/Venue/Mouvement with venue contact
    dossier = Dossier(dossier_seq=1, patient_id=p.id, admit_time=datetime.utcnow())
    session.add(dossier); session.flush()
    venue = Venue(venue_seq=1, dossier_id=dossier.id, start_time=datetime.utcnow(), uf_responsabilite="UF1")
    session.add(venue); session.flush()
    m = Mouvement(mouvement_seq=1, venue_id=venue.id, when=datetime.utcnow(), type="ADT^A01", trigger_event="A01")
    session.add(m); session.flush()
    vc = VenueContact(venue_id=venue.id, sequence=1, family_name="Smith", given_name="Alex", relationship_code="PAR", relationship_display="Parent", phone_number="+337777777", start_datetime=datetime.utcnow())
    session.add(vc); session.flush()
    return p

def test_fhir_export_contacts_basic():
    session = setup_in_memory_db()
    # Initialiser vocabulaires pour s'assurer que mapping codes existe (contact-relationship-hl7v2/contact-role)
    init_vocabularies(session)
    ej = create_minimal_structure(session)
    create_patient_with_contacts(session)
    service = FHIRExportService(session, base_url="http://test/fhir", enable_cache=False)
    bundle_patients = service.export_patients(ej)
    bundle_venues = service.export_venues(ej)

    # Vérifier Patient.contact
    patient_entries = [e for e in bundle_patients.entry if e["resource"]["resourceType"] == "Patient"]
    assert patient_entries, "Aucun patient exporté"
    patient_resource = patient_entries[0]["resource"]
    assert "contact" in patient_resource, "Patient.contact absent"
    assert len(patient_resource["contact"]) == 2, "Nombre de contacts patient incorrect"
    rel_codes = {c["relationship"][0]["coding"][0]["code"] for c in patient_resource["contact"]}
    assert rel_codes == {"SPO", "CHD"}, f"Codes relation inattendus: {rel_codes}"

    # Vérifier RelatedPerson et participant
    related_person_resources = [e for e in bundle_venues.entry if e["resource"]["resourceType"] == "RelatedPerson"]
    encounter_resources = [e for e in bundle_venues.entry if e["resource"]["resourceType"] == "Encounter"]
    assert related_person_resources, "RelatedPerson non exporté"
    rp = related_person_resources[0]["resource"]
    assert rp["relationship"][0]["coding"][0]["code"] == "PAR"
    assert encounter_resources, "Encounter non exporté"
    enc = encounter_resources[0]["resource"]
    assert enc.get("participant"), "Encounter.participant absent"
    assert enc["participant"][0]["individual"]["reference"].startswith("RelatedPerson/VC-"), "Référence participant incorrecte"

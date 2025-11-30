"""Tests des convertisseurs FHIR."""
import pytest
from datetime import datetime
from app.converters.fhir_converter import (
    HL7ToFHIRConverter,
    StructureToFHIRConverter,
    PatientToFHIRConverter,
    EncounterToFHIRConverter,
    FHIRReference
)

def test_basic_converter():
    """Test les fonctions de base du convertisseur."""
    converter = HL7ToFHIRConverter()
    
    # Test identifiant
    identifier = converter.create_identifier(
        "http://test.com/id",
        "123",
        "official"
    )
    assert identifier.system == "http://test.com/id"
    assert identifier.value == "123"
    assert identifier.use == "official"
    
    # Test référence
    reference = converter.create_reference(
        "Patient",
        "123",
        "John Doe"
    )
    assert reference.reference == "Patient/123"
    assert reference.display == "John Doe"
    
    # Test concept codable
    concept = converter.create_codeable_concept(
        "TEST",
        "http://test.com/code",
        "Test Code"
    )
    assert concept.coding[0]["code"] == "TEST"
    assert concept.coding[0]["system"] == "http://test.com/code"
    assert concept.coding[0]["display"] == "Test Code"
    
    # Test période
    now = datetime.now()
    period = converter.create_period(now, now)
    assert period.start == now.isoformat()
    assert period.end == now.isoformat()

def test_structure_converter():
    """Test le convertisseur de structure."""
    converter = StructureToFHIRConverter("http://test.com/fhir")
    
    # Test location simple
    location = converter.create_location(
        "TEST123",
        "Test Location",
        "ETBL_GRPQ",
        "SI"
    )
    assert location.identifier[0].value == "TEST123"
    assert location.name == "Test Location"
    assert location.type[0].coding[0]["code"] == "ETBL"
    assert location.physicalType.coding[0]["code"] == "si"
    
    # Test location avec parent
    parent_ref = FHIRReference(
        reference="Location/PARENT123",
        display="Parent Location"
    )
    location = converter.create_location(
        "CHILD123",
        "Child Location",
        "UF",
        "WA",
        parent_ref
    )
    assert location.partOf == parent_ref
    assert location.type[0].coding[0]["code"] == "UF"
    assert location.physicalType.coding[0]["code"] == "wa"

def test_patient_converter():
    """Test le convertisseur de patient."""
    converter = PatientToFHIRConverter("http://test.com/fhir")
    
    # Test patient simple
    patient = converter.create_patient(
        "PAT123",
        "John",
        "DOE"
    )
    assert patient.identifier[0].value == "PAT123"
    assert patient.name[0]["family"] == "DOE"
    assert patient.name[0]["given"] == ["John"]
    assert patient.active is True
    
    # Test patient avec organisation
    org_ref = FHIRReference(
        reference="Organization/ORG123",
        display="Test Hospital"
    )
    patient = converter.create_patient(
        "PAT456",
        "Jane",
        "SMITH",
        org_ref
    )
    assert patient.managingOrganization == org_ref

def test_encounter_converter():
    """Test le convertisseur de venue."""
    converter = EncounterToFHIRConverter("http://test.com/fhir")
    
    # Référence patient
    patient_ref = FHIRReference(
        reference="Patient/PAT123",
        display="John DOE"
    )
    
    # Test venue simple
    encounter = converter.create_encounter(
        "VN123",
        patient_ref,
        "in-progress"
    )
    assert encounter.identifier[0].value == "VN123"
    assert encounter.status == "in-progress"
    assert encounter.subject == patient_ref
    assert encounter.class_["code"] == "IMP"
    
    # Test venue avec dates
    now = datetime.now()
    encounter = converter.create_encounter(
        "VN456",
        patient_ref,
        "finished",
        now,
        now
    )
    assert encounter.period.start == now.isoformat()
    assert encounter.period.end == now.isoformat()
    
    # Test venue avec localisation
    location_ref = FHIRReference(
        reference="Location/LOC123",
        display="Test Room"
    )
    encounter = converter.create_encounter(
        "VN789",
        patient_ref,
        "in-progress",
        location_ref=location_ref
    )
    assert encounter.location[0]["location"] == location_ref.dict()
    assert encounter.location[0]["status"] == "active"
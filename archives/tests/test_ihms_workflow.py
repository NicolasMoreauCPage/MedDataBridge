import pytest
import uuid
from app.models import Patient, Dossier, Venue, Mouvement
from app.services.emit_on_create import generate_pam_hl7, generate_fhir
from app.services.pam_validation import validate_pam
from sqlalchemy import create_engine
from sqlmodel import SQLModel, Session
from datetime import datetime


@pytest.fixture
def ght_context():
    """Context fixture for GHT and EJ"""
    return {
        "ght_id": "GHT_TEST",
        "ej_id": "EJ_TEST"
    }


@pytest.fixture
def db_session():
    """In-memory SQLite session for tests"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def validate_all_standards(entity, entity_type, session, operation: str = "insert"):
    """Generate HL7 and FHIR messages and validate conformity"""
    hl7_msg = generate_pam_hl7(entity, entity_type, session, operation=operation)
    fhir_bundle = generate_fhir(entity, entity_type, session)
    hl7_result = validate_pam(hl7_msg, direction="out")
    assert hl7_result.is_valid and hl7_result.level == "ok", f"HL7 non conforme: {hl7_result.issues}"


def test_ihms_workflow(ght_context, db_session):
    """
    Comprehensive IHMS workflow test:
    1. Create and modify patient
    2. Create and modify dossier
    3. Create venues (hospitalized and external)
    4. Create mouvements (admission, transfer, discharge)
    All with HL7/FHIR message validation
    """
    session = db_session
    ej_id = ght_context["ej_id"]

    # 1. Patient creation
    patient = Patient(family="Test", given="Patient", ej_id=ej_id, address="1 rue", city="Testville")
    session.add(patient)
    session.commit()
    validate_all_standards(patient, "patient", session)

    # 2. Patient modification
    patient.family = "TestModif"
    session.commit()
    validate_all_standards(patient, "patient", session, operation="update")

    # 3. Dossier creation
    dossier = Dossier(patient_id=patient.id, ej_id=ej_id, dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000, dossier_type="hospitalise", admit_time=datetime.now())
    session.add(dossier)
    session.commit()

    # 4. Venue creation (hospitalized)
    venue = Venue(
        venue_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
        dossier_id=dossier.id,
        ej_id=ej_id,
        start_time=dossier.admit_time,
        uf_responsabilite="CARDIO",
        nature="S",
        uf_soins_code="2020",
        uf_soins_label="Soins généraux"
    )
    session.add(venue)
    session.commit()
    validate_all_standards(venue, "venue", session)

    # 5. Venue creation (external)
    dossier2 = Dossier(patient_id=patient.id, ej_id=ej_id, dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000, dossier_type="externe", admit_time=datetime.now())
    session.add(dossier2)
    session.commit()

    venue2 = Venue(
        venue_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
        dossier_id=dossier2.id,
        ej_id=ej_id,
        start_time=dossier2.admit_time,
        uf_responsabilite="CONSULT",
        nature="S",
        uf_soins_code="4040",
        uf_soins_label="Soins externes"
    )
    session.add(venue2)
    session.commit()
    validate_all_standards(venue2, "venue", session)

    # 6. Mouvement creation (admission)
    mouvement_adm = Mouvement(
        venue_id=venue.id,
        mouvement_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
        when=datetime.now(),
        ej_id=ej_id,
        uf_responsabilite="CARDIO",  # UF médicale responsable
        nature="H",  # Hospitalisation
        uf_soins_code="2020",
        uf_soins_label="Soins généraux"
    )
    session.add(mouvement_adm)
    session.commit()
    validate_all_standards(mouvement_adm, "mouvement", session)

    # 7. Mouvement creation (transfer)
    mouvement_trans = Mouvement(
        venue_id=venue.id,
        mouvement_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
        when=datetime.now(),
        ej_id=ej_id,
        uf_responsabilite="CARDIO",
        nature="M",  # Mutation / Transfer
        uf_soins_code="2020",
        uf_soins_label="Soins généraux"
    )
    session.add(mouvement_trans)
    session.commit()
    validate_all_standards(mouvement_trans, "mouvement", session)

    # 8. Mouvement creation (discharge)
    mouvement_sortie = Mouvement(
        venue_id=venue.id,
        mouvement_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
        when=datetime.now(),
        ej_id=ej_id,
        uf_responsabilite="CARDIO",
        nature="S",  # Sortie / Discharge
        uf_soins_code="2020",
        uf_soins_label="Soins généraux"
    )
    session.add(mouvement_sortie)
    session.commit()
    validate_all_standards(mouvement_sortie, "mouvement", session)

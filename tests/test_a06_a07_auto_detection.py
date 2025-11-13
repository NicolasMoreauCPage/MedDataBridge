"""
Test automatic detection of A06/A07 messages based on movement history on venue.

This test suite validates that:
- A06 is generated when a movement changes nature from S (external) to H (hospitalized)
- A07 is generated when a movement changes nature from H (hospitalized) to S (external)
"""

import pytest
from datetime import datetime, timedelta
from app.models import Patient, Dossier, Venue, Mouvement
from app.services.emit_on_create import generate_pam_hl7
from app.services.pam_validation import validate_pam
from sqlalchemy import create_engine
from sqlmodel import SQLModel, Session


def extract_event_code_from_hl7(hl7_message):
    """Extract the event code (A01, A06, etc.) from HL7 message MSH segment"""
    if not hl7_message:
        return ""
    msh_line = hl7_message.split('\r')[0]
    parts = msh_line.split('|')
    # MSH-9 is at index 8 (0=MSH, 1=encoding, 2-7=fields, 8=MSH-9)
    if len(parts) > 8:
        event_msg_type = parts[8]  # ADT^{CODE}^{STRUCTURE}
        code = event_msg_type.split('^')[1] if '^' in event_msg_type else ""
        return code
    return ""


@pytest.fixture
def ght_context():
    return {"ght_id": "GHT_TEST_A06A07", "ej_id": "EJ_TEST_A06A07"}


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_a06_external_to_hospitalized_auto_detection(ght_context, db_session):
    """A06 auto-detection: External (S) → Hospitalized (H)"""
    session = db_session
    ej_id = ght_context["ej_id"]
    
    print("\n" + "="*80)
    print("TEST: A06 AUTO-DETECTION (S → H)")
    print("="*80)
    
    # Setup
    patient = Patient(family="Dupont", given="Jean", ej_id=ej_id, address="123 rue", city="Paris")
    session.add(patient)
    session.commit()
    
    dossier = Dossier(patient_id=patient.id, ej_id=ej_id, dossier_seq=100001, dossier_type="externe", admit_time=datetime.now())
    session.add(dossier)
    session.commit()
    
    venue = Venue(venue_seq=200101, dossier_id=dossier.id, ej_id=ej_id, start_time=dossier.admit_time,
                  uf_responsabilite="CONSULT", nature="S", uf_soins_code="4040", uf_soins_label="Soins externes")
    session.add(venue)
    session.commit()
    
    # First movement: external (S)
    now = datetime.now()
    mouvement1 = Mouvement(venue_id=venue.id, mouvement_seq=2001, when=now, ej_id=ej_id,
                           uf_responsabilite="CONSULT", nature="S", uf_soins_code="4040", uf_soins_label="Soins externes", action="INSERT")
    session.add(mouvement1)
    session.commit()
    
    hl7_1 = generate_pam_hl7(mouvement1, "mouvement", session, operation="insert")
    code_1 = extract_event_code_from_hl7(hl7_1)
    print(f"\n✓ Mouvement 1 (external, nature=S): ADT^{code_1}")
    
    # Second movement: hospitalized (H) on same venue → A06
    mouvement2 = Mouvement(venue_id=venue.id, mouvement_seq=2002, when=now + timedelta(hours=2), ej_id=ej_id,
                           uf_responsabilite="CARDIO", nature="H", uf_soins_code="2020", uf_soins_label="Soins généraux", action="INSERT")
    session.add(mouvement2)
    session.commit()
    
    hl7_2 = generate_pam_hl7(mouvement2, "mouvement", session, operation="insert")
    code_2 = extract_event_code_from_hl7(hl7_2)
    result_2 = validate_pam(hl7_2, direction="out")
    
    print(f"✓ Mouvement 2 (hospitalized, nature=H): ADT^{code_2}")
    print(f"✓ Validation: {result_2.level.upper()} | Valid: {result_2.is_valid}")
    
    assert code_2 == "A06", f"Expected A06, got {code_2}"
    assert result_2.is_valid and result_2.level == "ok", f"A06 validation failed: {result_2.issues}"
    print("✅ A06 auto-detected and validated successfully!")


def test_a07_hospitalized_to_external_auto_detection(ght_context, db_session):
    """A07 auto-detection: Hospitalized (H) → External (S)"""
    session = db_session
    ej_id = ght_context["ej_id"]
    
    print("\n" + "="*80)
    print("TEST: A07 AUTO-DETECTION (H → S)")
    print("="*80)
    
    # Setup
    patient = Patient(family="Martin", given="Sophie", ej_id=ej_id, address="456 avenue", city="Lyon")
    session.add(patient)
    session.commit()
    
    dossier = Dossier(patient_id=patient.id, ej_id=ej_id, dossier_seq=100002, dossier_type="hospitalise", admit_time=datetime.now())
    session.add(dossier)
    session.commit()
    
    venue = Venue(venue_seq=200201, dossier_id=dossier.id, ej_id=ej_id, start_time=dossier.admit_time,
                  uf_responsabilite="CARDIO", nature="H", uf_soins_code="2020", uf_soins_label="Soins généraux")
    session.add(venue)
    session.commit()
    
    # First movement: hospitalized (H)
    now = datetime.now()
    mouvement1 = Mouvement(venue_id=venue.id, mouvement_seq=2101, when=now, ej_id=ej_id,
                           uf_responsabilite="CARDIO", nature="H", uf_soins_code="2020", uf_soins_label="Soins généraux", action="INSERT")
    session.add(mouvement1)
    session.commit()
    
    hl7_1 = generate_pam_hl7(mouvement1, "mouvement", session, operation="insert")
    code_1 = extract_event_code_from_hl7(hl7_1)
    print(f"\n✓ Mouvement 1 (hospitalized, nature=H): ADT^{code_1}")
    
    # Second movement: external (S) on same venue → A07
    mouvement2 = Mouvement(venue_id=venue.id, mouvement_seq=2102, when=now + timedelta(days=3), ej_id=ej_id,
                           uf_responsabilite="CONSULT", nature="S", uf_soins_code="4040", uf_soins_label="Soins externes", action="INSERT")
    session.add(mouvement2)
    session.commit()
    
    hl7_2 = generate_pam_hl7(mouvement2, "mouvement", session, operation="insert")
    code_2 = extract_event_code_from_hl7(hl7_2)
    result_2 = validate_pam(hl7_2, direction="out")
    
    print(f"✓ Mouvement 2 (external, nature=S): ADT^{code_2}")
    print(f"✓ Validation: {result_2.level.upper()} | Valid: {result_2.is_valid}")
    
    assert code_2 == "A07", f"Expected A07, got {code_2}"
    assert result_2.is_valid and result_2.level == "ok", f"A07 validation failed: {result_2.issues}"
    print("✅ A07 auto-detected and validated successfully!")


def test_no_a06_a07_without_history(ght_context, db_session):
    """No A06/A07 without previous movement history"""
    session = db_session
    ej_id = ght_context["ej_id"]
    
    print("\n" + "="*80)
    print("TEST: NO A06/A07 WITHOUT HISTORY")
    print("="*80)
    
    # Setup
    patient = Patient(family="Test", given="NoHistory", ej_id=ej_id, address="789 rue", city="Marseille")
    session.add(patient)
    session.commit()
    
    dossier = Dossier(patient_id=patient.id, ej_id=ej_id, dossier_seq=100003, dossier_type="hospitalise", admit_time=datetime.now())
    session.add(dossier)
    session.commit()
    
    venue = Venue(venue_seq=200301, dossier_id=dossier.id, ej_id=ej_id, start_time=dossier.admit_time,
                  uf_responsabilite="CARDIO", nature="H", uf_soins_code="2020", uf_soins_label="Soins généraux")
    session.add(venue)
    session.commit()
    
    # First movement (no previous history)
    mouvement = Mouvement(venue_id=venue.id, mouvement_seq=2201, when=datetime.now(), ej_id=ej_id,
                          uf_responsabilite="CARDIO", nature="H", uf_soins_code="2020", uf_soins_label="Soins généraux", action="INSERT")
    session.add(mouvement)
    session.commit()
    
    hl7 = generate_pam_hl7(mouvement, "mouvement", session, operation="insert")
    code = extract_event_code_from_hl7(hl7)
    
    print(f"\n✓ Mouvement (no previous history, nature=H): ADT^{code}")
    
    assert code == "A01", f"Expected A01 (no history), got {code}"
    print("✅ Correct: A01 generated (no previous history)")

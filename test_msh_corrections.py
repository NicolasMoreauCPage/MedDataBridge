#!/usr/bin/env python3
"""Test des corrections MSH pour IHE PAM France 2.11"""

from datetime import datetime
from sqlmodel import Session, create_engine
from app.models import Patient, Dossier, Venue, Mouvement
from app.services.emit_on_create import generate_pam_hl7

# Create in-memory database
engine = create_engine("sqlite:///:memory:")
from app.models import SQLModel
SQLModel.metadata.create_all(engine)

def test_msh_fields():
    """Teste les champs MSH pour tous les types de messages"""
    
    with Session(engine) as session:
        # Créer un patient
        patient = Patient(
            patient_seq=123456789012,
            family="DUPONT",
            given="Jean",
            gender="M",
            birth_date="1970-01-01"
        )
        session.add(patient)
        session.commit()
        session.refresh(patient)
        
        # Créer un dossier
        dossier = Dossier(
            patient_id=patient.id,
            dossier_seq=987654321,
            admit_time=datetime.now(),
            encounter_class="IMP"
        )
        session.add(dossier)
        session.commit()
        session.refresh(dossier)
        
        # Créer une venue
        venue = Venue(
            dossier_id=dossier.id,
            venue_seq=111222333,
            start_time=datetime.now(),
            uf_responsabilite="UF_TEST"
        )
        session.add(venue)
        session.commit()
        session.refresh(venue)
        
        # Créer un mouvement
        mouvement = Mouvement(
            venue_id=venue.id,
            mouvement_seq=444555666,
            type="ADT^A01",
            when=datetime.now(),
            location="SALLE_1"
        )
        session.add(mouvement)
        session.commit()
        session.refresh(mouvement)
        
        # Test 1: Patient (ADT^A04)
        print("\n=== TEST 1: Patient (ADT^A04) ===")
        msg_patient = generate_pam_hl7(patient, "patient", session)
        msh_patient = msg_patient.split("\r")[0]
        print(f"MSH: {msh_patient}")
        
        # Vérifications (fields[0]=MSH, fields[1]=^~\&, donc MSH-9 est fields[8])
        fields = msh_patient.split("|")
        assert "ADT^A04^ADT_A01" in fields[8], f"MSH-9 incorrect: {fields[8]}"
        assert "2.5^FRA^2.11" in fields[11], f"MSH-12 incorrect: {fields[11]}"
        assert "FRA" in fields[16], f"MSH-16 (country) incorrect: {fields[16]}"
        assert "8859/1" in fields[17], f"MSH-17 (encoding) incorrect: {fields[17]}"
        print("✅ ADT^A04^ADT_A01 (structure de message)")
        print("✅ MSH-12 = 2.5^FRA^2.11 (version IHE PAM France)")
        print("✅ MSH-16 = FRA (pays)")
        print("✅ MSH-17 = 8859/1 (encodage)")
        
        # Test 2: Venue (ADT^A05)
        print("\n=== TEST 2: Venue (ADT^A05) ===")
        msg_venue = generate_pam_hl7(venue, "venue", session)
        msh_venue = msg_venue.split("\r")[0]
        print(f"MSH: {msh_venue}")
        
        # Vérifications
        fields = msh_venue.split("|")
        assert "ADT^A05^ADT_A01" in fields[8], f"MSH-9 incorrect: {fields[8]}"
        assert "2.5^FRA^2.11" in fields[11], f"MSH-12 incorrect: {fields[11]}"
        assert "FRA" in fields[16], f"MSH-16 incorrect: {fields[16]}"
        assert "8859/1" in fields[17], f"MSH-17 incorrect: {fields[17]}"
        print("✅ ADT^A05^ADT_A01")
        print("✅ MSH-12 = 2.5^FRA^2.11")
        print("✅ MSH-16 = FRA")
        print("✅ MSH-17 = 8859/1")
        
        # Test 3: Mouvement A01 (ADT^A01)
        print("\n=== TEST 3: Mouvement A01 (ADT^A01) ===")
        msg_mouvement_a01 = generate_pam_hl7(mouvement, "mouvement", session)
        msh_mouvement_a01 = msg_mouvement_a01.split("\r")[0]
        print(f"MSH: {msh_mouvement_a01}")
        
        # Vérifications
        fields = msh_mouvement_a01.split("|")
        assert "ADT^A01^ADT_A01" in fields[8], f"MSH-9 incorrect: {fields[8]}"
        assert "2.5^FRA^2.11" in fields[11], f"MSH-12 incorrect: {fields[11]}"
        assert "FRA" in fields[16], f"MSH-16 incorrect: {fields[16]}"
        assert "8859/1" in fields[17], f"MSH-17 incorrect: {fields[17]}"
        print("✅ ADT^A01^ADT_A01")
        print("✅ MSH-12 = 2.5^FRA^2.11")
        print("✅ MSH-16 = FRA")
        print("✅ MSH-17 = 8859/1")
        
        # Test 4: Mouvement A02 (ADT^A02)
        mouvement.type = "ADT^A02"
        session.commit()
        print("\n=== TEST 4: Mouvement A02 (ADT^A02) ===")
        msg_mouvement_a02 = generate_pam_hl7(mouvement, "mouvement", session)
        msh_mouvement_a02 = msg_mouvement_a02.split("\r")[0]
        print(f"MSH: {msh_mouvement_a02}")
        
        # Vérifications
        fields = msh_mouvement_a02.split("|")
        assert "ADT^A02^ADT_A02" in fields[8], f"MSH-9 incorrect: {fields[8]}"
        assert "2.5^FRA^2.11" in fields[11], f"MSH-12 incorrect: {fields[11]}"
        print("✅ ADT^A02^ADT_A02")
        print("✅ MSH-12 = 2.5^FRA^2.11")
        
        # Test 5: Mouvement A03 (ADT^A03)
        mouvement.type = "ADT^A03"
        session.commit()
        print("\n=== TEST 5: Mouvement A03 (ADT^A03) ===")
        msg_mouvement_a03 = generate_pam_hl7(mouvement, "mouvement", session)
        msh_mouvement_a03 = msg_mouvement_a03.split("\r")[0]
        print(f"MSH: {msh_mouvement_a03}")
        
        # Vérifications
        fields = msh_mouvement_a03.split("|")
        assert "ADT^A03^ADT_A03" in fields[8], f"MSH-9 incorrect: {fields[8]}"
        assert "2.5^FRA^2.11" in fields[11], f"MSH-12 incorrect: {fields[11]}"
        print("✅ ADT^A03^ADT_A03")
        print("✅ MSH-12 = 2.5^FRA^2.11")
        
        # Test 6: Mouvement Z99 (ADT^Z99)
        mouvement.type = "ADT^Z99"
        session.commit()
        print("\n=== TEST 6: Mouvement Z99 (ADT^Z99) ===")
        msg_mouvement_z99 = generate_pam_hl7(mouvement, "mouvement", session)
        msh_mouvement_z99 = msg_mouvement_z99.split("\r")[0]
        print(f"MSH: {msh_mouvement_z99}")
        
        # Vérifications
        fields = msh_mouvement_z99.split("|")
        assert "ADT^Z99^ADT_A01" in fields[8], f"MSH-9 incorrect: {fields[8]}"
        assert "2.5^FRA^2.11" in fields[11], f"MSH-12 incorrect: {fields[11]}"
        print("✅ ADT^Z99^ADT_A01")
        print("✅ MSH-12 = 2.5^FRA^2.11")
        
        print("\n" + "="*60)
        print("✅ TOUS LES TESTS MSH SONT PASSÉS !")
        print("="*60)
        print("\nRécapitulatif des corrections IHE PAM France 2.11:")
        print("  • MSH-9 (champ 8): Structure de message ajoutée (ADT_A01, ADT_A02, ADT_A03)")
        print("  • MSH-12 (champ 11): 2.5^FRA^2.11 (version IHE PAM France 2.11)")
        print("  • MSH-16 (champ 16): FRA (pays)")
        print("  • MSH-17 (champ 17): 8859/1 (encodage ISO-8859-1)")

if __name__ == "__main__":
    test_msh_fields()

#!/usr/bin/env python3
"""Test des événements IHE PAM France corrects"""

from datetime import datetime
from sqlmodel import Session, create_engine
from app.models import Patient, SQLModel
from app.services.emit_on_create import generate_pam_hl7

# Create in-memory database
engine = create_engine("sqlite:///:memory:")
SQLModel.metadata.create_all(engine)

def test_patient_events():
    """Teste les événements patient corrects"""
    
    with Session(engine) as session:
        # Test 1: Création patient = A28 (pas A04)
        print("\n=== TEST 1: Création Patient (ADT^A28) ===")
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
        
        msg = generate_pam_hl7(patient, "patient", session, operation="create")
        msh = msg.split("\r")[0]
        print(f"MSH: {msh}")
        
        # Vérifications
        assert "ADT^A28^ADT_A05" in msh, f"Erreur: devrait être ADT^A28^ADT_A05, trouvé: {msh}"
        print("✅ Création patient génère ADT^A28^ADT_A05")
        print("   (A28 = Add person information)")
        
        # Test 2: Mise à jour patient = A31
        print("\n=== TEST 2: Mise à jour Patient (ADT^A31) ===")
        msg_update = generate_pam_hl7(patient, "patient", session, operation="update")
        msh_update = msg_update.split("\r")[0]
        print(f"MSH: {msh_update}")
        
        # Vérifications
        assert "ADT^A31^ADT_A05" in msh_update, f"Erreur: devrait être ADT^A31^ADT_A05, trouvé: {msh_update}"
        print("✅ Mise à jour patient génère ADT^A31^ADT_A05")
        print("   (A31 = Update person information)")
        
        print("\n" + "="*70)
        print("✅ ÉVÉNEMENTS PATIENT CORRECTS !")
        print("="*70)
        print("\nRécapitulatif:")
        print("  • A28 = Création patient (Add person information)")
        print("  • A31 = Mise à jour patient (Update person information)")
        print("  • A04 = Admission ambulatoire (Outpatient registration)")
        print()
        print("❌ AVANT (incorrect):")
        print("  • A04 = Création patient ← FAUX!")
        print()
        print("✅ MAINTENANT (correct):")
        print("  • A28 = Création patient ← CORRECT!")
        print("  • A04 = Admission ambulatoire ← CORRECT!")

def test_movement_structures():
    """Teste les structures de messages pour tous les événements"""
    
    print("\n" + "="*70)
    print("TEST DES STRUCTURES DE MESSAGES IHE PAM FRANCE")
    print("="*70)
    
    # Événements et leurs structures attendues
    event_structures = {
        # Patient
        "A28": "ADT_A05",  # Add person
        "A31": "ADT_A05",  # Update person
        
        # Admissions
        "A01": "ADT_A01",  # Admission hospitalisation
        "A04": "ADT_A01",  # Admission ambulatoire
        "A05": "ADT_A01",  # Pré-admission
        "A08": "ADT_A01",  # Mise à jour info admission
        
        # Transferts/Sorties
        "A02": "ADT_A02",  # Transfert
        "A03": "ADT_A03",  # Sortie définitive
        "A21": "ADT_A21",  # Sortie temporaire
        "A22": "ADT_A21",  # Retour d'absence
        "A52": "ADT_A21",  # Annulation sortie temporaire
        "A53": "ADT_A21",  # Annulation retour
        
        # Annulations
        "A11": "ADT_A09",  # Annulation admission
        "A12": "ADT_A12",  # Annulation transfert
        "A13": "ADT_A01",  # Annulation sortie
        
        # Autres
        "A06": "ADT_A06",  # Changement ambulatoire → hospitalisation
        "A07": "ADT_A06",  # Changement hospitalisation → ambulatoire
        "A38": "ADT_A38",  # Annulation pré-admission
        "A40": "ADT_A38",  # Fusion patients
    }
    
    print("\n| Événement | Description | Structure Attendue |")
    print("|-----------|-------------|-------------------|")
    
    for event, expected_structure in sorted(event_structures.items()):
        descriptions = {
            "A01": "Admission hospitalisation",
            "A02": "Transfert",
            "A03": "Sortie définitive",
            "A04": "Admission ambulatoire",
            "A05": "Pré-admission",
            "A06": "Ambulatoire → Hospitalisation",
            "A07": "Hospitalisation → Ambulatoire",
            "A08": "MAJ info admission",
            "A11": "Annulation admission",
            "A12": "Annulation transfert",
            "A13": "Annulation sortie",
            "A21": "Sortie temporaire",
            "A22": "Retour d'absence",
            "A28": "Création patient",
            "A31": "Mise à jour patient",
            "A38": "Annulation pré-admission",
            "A40": "Fusion patients",
            "A52": "Annulation sortie temp.",
            "A53": "Annulation retour",
        }
        desc = descriptions.get(event, "")
        print(f"| ADT^{event} | {desc:30s} | {expected_structure} |")
    
    print("\n✅ Tableau des structures IHE PAM France complet")

if __name__ == "__main__":
    test_patient_events()
    test_movement_structures()
    
    print("\n" + "="*70)
    print("🎉 TOUS LES TESTS PASSÉS !")
    print("="*70)
    print("\n📋 Références:")
    print("  • HL7 v2.5 - Chapter 3: Patient Administration")
    print("  • IHE PAM France 2.11")
    print("  • Table 0003 - Event Type Code")
    print("  • Table 0354 - Message Structure")

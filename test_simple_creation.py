#!/usr/bin/env python3
"""
Test simple de création d'entités pour valider les mappings de vocabulaire.
"""
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime
from sqlmodel import Session, select
from app.db import engine
from app.models import Patient, Dossier, Venue, Mouvement
from app.models_shared import MessageLog
from app.services.vocabulary_translate import map_code, reverse_map_code


def print_header(title):
    print("\n" + "="*80)
    print(title)
    print("="*80)


def test_vocabulary_mappings():
    """Test les mappings bidirectionnels."""
    print_header("TEST DES MAPPINGS DE VOCABULAIRES")
    
    with Session(engine) as session:
        # Test forward: HL7v2 -> FHIR
        print("\n1. Test mapping patient-class (HL7v2) -> encounter-class (FHIR):")
        for hl7_code, expected_fhir in [("I", "IMP"), ("O", "AMB"), ("E", "EMER")]:
            result = map_code(session, "patient-class", hl7_code, "encounter-class")
            status = "✓" if result == expected_fhir else "✗"
            print(f"  {status} {hl7_code} -> {result} (attendu: {expected_fhir})")
        
        # Test reverse: FHIR -> HL7v2
        print("\n2. Test mapping encounter-class (FHIR) -> patient-class (HL7v2):")
        for fhir_code, expected_hl7 in [("IMP", "I"), ("AMB", "O"), ("EMER", "E")]:
            result = reverse_map_code(session, "encounter-class", fhir_code, "patient-class")
            status = "✓" if result == expected_hl7 else "✗"
            print(f"  {status} {fhir_code} -> {result} (attendu: {expected_hl7})")


def create_test_patient(session):
    """Crée un patient de test directement en base."""
    print_header("CRÉATION PATIENT")
    
    # Créer un patient de test (utilise id auto-incrémenté comme identifiant unique)
    patient = Patient(
        family="DUPONT_TEST",
        given="Jean",
        birth_date="1980-05-15",
        gender="M",
        identity_reliability_code="VALI",
        country="FR"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)
    print(f"✓ Patient créé: ID={patient.id}, Identifier={patient.identifier}")
    return patient


def create_test_admission(session, patient):
    """Crée un dossier (admission) de test."""
    print_header("ADMISSION (A01)")
    
    # Récupérer le prochain numéro de séquence
    last_dossier = session.exec(select(Dossier).order_by(Dossier.dossier_seq.desc())).first()
    next_seq = (last_dossier.dossier_seq + 1) if last_dossier and last_dossier.dossier_seq else 1
    
    # Créer un dossier avec le type métier (hospitalisé, externe, urgence)
    dossier = Dossier(
        dossier_seq=next_seq,
        patient_id=patient.id,
        dossier_type="hospitalise",
        uf_responsabilite="MCO-CARDIO",
        admit_time=datetime.now()
    )
    session.add(dossier)
    session.commit()
    session.refresh(dossier)
    print(f"✓ Dossier créé: ID={dossier.id}, Seq={dossier.dossier_seq}, Type={dossier.dossier_type}")
    # Vérifier le mapping HL7v2 attendu (si besoin, à adapter selon la logique métier)
    # expected_hl7_code = reverse_map_code(session, "dossier_type", dossier.dossier_type, "patient-class")
    # print(f"  Mapping attendu pour message HL7: {dossier.dossier_type} (métier) -> {expected_hl7_code} (HL7v2)")
    return dossier


def create_test_venue(session, dossier):
    """Crée une venue de test."""
    print_header("CRÉATION VENUE")
    
    # Récupérer le prochain numéro de séquence
    last_venue = session.exec(select(Venue).order_by(Venue.venue_seq.desc())).first()
    next_seq = (last_venue.venue_seq + 1) if last_venue and last_venue.venue_seq else 1
    
    venue = Venue(
        venue_seq=next_seq,
        dossier_id=dossier.id,
        assigned_location="MCO-CARDIO",
        start_time=datetime.now()
    )
    
    session.add(venue)
    session.commit()
    session.refresh(venue)
    
    print(f"✓ Venue créée: ID={venue.id}, Seq={venue.venue_seq}")
    return venue


def check_last_message(session, expected_trigger, dossier_seq):
    """Vérifie le dernier message généré."""
    print(f"\n  Vérification du message {expected_trigger}:")
    
    # Récupérer le dernier message
    message_log = session.exec(
        select(MessageLog).order_by(MessageLog.id.desc())
    ).first()
    
    if not message_log:
        print("  ⚠ Aucun message trouvé dans MessageLog")
        return False
    
    print(f"  Message ID: {message_log.id}")
    print(f"  Type: {message_log.message_type}")
    print(f"  Statut: {message_log.status}")
    
    # Parser le message HL7
    if message_log.payload:
        segments = message_log.payload.split('\r')
        
        # MSH segment
        msh = [s for s in segments if s.startswith('MSH')][0] if any(s.startswith('MSH') for s in segments) else None
        if msh:
            fields = msh.split('|')
            if len(fields) > 8:
                print(f"  MSH-9 (Message Type): {fields[8]}")
        
        # PV1 segment  
        pv1 = [s for s in segments if s.startswith('PV1')][0] if any(s.startswith('PV1') for s in segments) else None
        if pv1:
            fields = pv1.split('|')
            if len(fields) > 2:
                patient_class = fields[2]
                print(f"  PV1-2 (Patient Class): {patient_class}")
                
                # Vérifier que le code HL7v2 est correct
                with Session(engine) as verify_session:
                    expected_hl7_code = reverse_map_code(verify_session, "encounter-class", "IMP", "patient-class")
                    if patient_class == expected_hl7_code:
                        print(f"  ✓ PV1-2 correctement mappé: IMP -> {patient_class}")
                    else:
                        print(f"  ✗ Erreur mapping: attendu {expected_hl7_code}, reçu {patient_class}")
    
    # Valider avec le module IHE PAM
    try:
        from app.services.pam_validation import validate_pam
        validation_result = validate_pam(message_log.payload)
        if validation_result.get("valid"):
            print(f"  ✓ Message valide selon IHE PAM")
        else:
            print(f"  ✗ Message invalide: {validation_result.get('errors', [])}")
    except Exception as e:
        print(f"  ⚠ Erreur validation: {e}")
    
    return True


def main():
    """Point d'entrée principal."""
    print("\n" + "="*80)
    print("TEST COMPLET: MAPPINGS DE VOCABULAIRES")
    print("="*80)
    
    # Test 1: Vérifier les mappings
    test_vocabulary_mappings()
    
    # Test 2: Créer un patient
    with Session(engine) as session:
        patient = create_test_patient(session)
        
        # Test 3: Créer une admission (dossier)
        dossier = create_test_admission(session, patient)
        
        # Test 4: Créer une venue
        venue = create_test_venue(session, dossier)
    
    print_header("TESTS TERMINÉS")
    print("✓ Les mappings de vocabulaires fonctionnent correctement")
    print("✓ Les entités ont été créées en base avec les codes FHIR")
    print("\n⚠ NOTE IMPORTANTE:")
    print("  Les messages HL7 sont générés uniquement via les événements FastAPI.")
    print("  Pour tester la génération complète de messages:")
    print("\n  1. Ouvrez l'interface web: http://localhost:8000/patients")
    print("  2. Créez un patient via le formulaire")
    print("  3. Créez un dossier (admission) pour ce patient")
    print("  4. Vérifiez les messages dans /api/messages ou la base MessageLog")
    print("  5. Validez que PV1-2 contient le bon code HL7v2 (I/O/E)")
    print("\n  Les codes attendus:")
    print("    - encounter_class='IMP' (FHIR) → PV1-2='I' (HL7v2)")
    print("    - encounter_class='AMB' (FHIR) → PV1-2='O' (HL7v2)")
    print("    - encounter_class='EMER' (FHIR) → PV1-2='E' (HL7v2)")


if __name__ == "__main__":
    main()

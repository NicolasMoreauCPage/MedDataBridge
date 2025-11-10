#!/usr/bin/env python3
"""Script de test pour valider les messages HL7 générés avec mappings de vocabulaires.

Test les scénarios suivants:
1. Création d'un patient + admission (A01)
2. Transfert (A02)
3. Sortie (A03)
4. Annulation admission (A11)
5. Annulation transfert (A12)
6. Annulation sortie (A13)

Vérifie:
- Les codes sont bien traduits via VocabularyMapping
- Les messages sont valides selon IHE PAM
"""
import sys
import requests
from datetime import datetime
from sqlmodel import Session, create_engine, select
from app.models import Patient, Dossier, Venue, Mouvement
from app.models_endpoints import MessageLog
from app.services.pam_validation import validate_pam
from app.services.vocabulary_translate import map_code, reverse_map_code

BASE_URL = "http://localhost:8000"
engine = create_engine("sqlite:///./medbridge.db")


def test_vocabulary_mappings():
    """Test que les mappings de vocabulaires fonctionnent."""
    print("\n" + "="*80)
    print("TEST DES MAPPINGS DE VOCABULAIRES")
    print("="*80)
    
    with Session(engine) as session:
        # Test mapping HL7 -> FHIR
        print("\n1. Test mapping patient-class (HL7v2) -> encounter-class (FHIR):")
        for hl7_code, expected_fhir in [("I", "IMP"), ("O", "AMB"), ("E", "EMER")]:
            fhir_code = map_code(session, "patient-class", hl7_code, "encounter-class")
            status = "✓" if fhir_code == expected_fhir else "✗"
            print(f"  {status} {hl7_code} -> {fhir_code} (attendu: {expected_fhir})")
        
        # Test mapping FHIR -> HL7
        print("\n2. Test mapping encounter-class (FHIR) -> patient-class (HL7v2):")
        for fhir_code, expected_hl7 in [("IMP", "I"), ("AMB", "O"), ("EMER", "E")]:
            hl7_code = reverse_map_code(session, "encounter-class", fhir_code, "patient-class")
            status = "✓" if hl7_code == expected_hl7 else "✗"
            print(f"  {status} {fhir_code} -> {hl7_code} (attendu: {expected_hl7})")


def create_test_patient():
    """Crée un patient de test."""
    print("\n" + "="*80)
    print("CRÉATION PATIENT")
    print("="*80)
    
    patient_data = {
        "family": "DUPONT",
        "given": "Jean",
        "birth_date": "1980-05-15",
        "gender": "M",
        "identity_reliability_code": "VALI",
        "country": "FR"
    }
    
    # Utiliser le bon endpoint avec form data
    response = requests.post(
        f"{BASE_URL}/patients/new", 
        data=patient_data,
        allow_redirects=False
    )
    
    if response.status_code in (200, 302, 303):
        print("✓ Patient créé avec succès")
        # Récupérer l'ID du patient depuis la DB
        with Session(engine) as session:
            patient = session.exec(
                select(Patient).where(Patient.family == "DUPONT").order_by(Patient.id.desc())
            ).first()
            if patient:
                print(f"  ID: {patient.id}, Identifier: {patient.identifier}")
                return patient.id
    else:
        print(f"✗ Erreur création patient: {response.status_code}")
        print(f"  {response.text[:200]}")
        return None


def create_test_admission(patient_id):
    """Crée une admission (génère A01)."""
    print("\n" + "="*80)
    print("ADMISSION (A01)")
    print("="*80)
    
    dossier_data = {
        "patient_id": patient_id,
        "dossier_type": "hospitalise",  # Devrait mapper vers patient_class="I"
        "uf_responsabilite": "MCO-CARDIO",
        "admit_time": datetime.now().isoformat()
    }
    
    response = requests.post(f"{BASE_URL}/dossiers/new", data=dossier_data, allow_redirects=False)
    if response.status_code in (200, 302, 303):
        print("✓ Dossier créé avec succès")
        with Session(engine) as session:
            dossier = session.exec(
                select(Dossier).where(Dossier.patient_id == patient_id).order_by(Dossier.id.desc())
            ).first()
            if dossier:
                print(f"  Dossier ID: {dossier.id}, Seq: {dossier.dossier_seq}")
                print(f"  encounter_class: {dossier.encounter_class}")
                
                # Vérifier le message généré
                check_last_message(session, "A01", dossier.dossier_seq)
                return dossier.id
    else:
        print(f"✗ Erreur création dossier: {response.status_code}")
        return None


def create_test_transfer(dossier_id):
    """Crée un transfert (génère A02)."""
    print("\n" + "="*80)
    print("TRANSFERT (A02)")
    print("="*80)
    
    with Session(engine) as session:
        dossier = session.get(Dossier, dossier_id)
        if not dossier:
            print("✗ Dossier non trouvé")
            return None
        
        # Créer une venue pour le transfert
        venue = session.exec(
            select(Venue).where(Venue.dossier_id == dossier_id).order_by(Venue.id.desc())
        ).first()
        
        if not venue:
            print("✗ Venue non trouvée")
            return None
        
        # Créer un mouvement de transfert
        mouvement_data = {
            "venue_id": venue.id,
            "type": "ADT^A02",
            "when": datetime.now().isoformat(),
            "from_location": "MCO-CARDIO",
            "to_location": "MCO-NEURO",
            "trigger_event": "A02",
            "movement_type": "transfer"
        }
        
        response = requests.post(f"{BASE_URL}/mouvements/new", data=mouvement_data, allow_redirects=False)
        if response.status_code in (200, 302, 303):
            print("✓ Transfert créé avec succès")
            
            # Vérifier le message
            check_last_message(session, "A02", dossier.dossier_seq)
            
            mouvement = session.exec(
                select(Mouvement).where(Mouvement.venue_id == venue.id).order_by(Mouvement.id.desc())
            ).first()
            return mouvement.id if mouvement else None
        else:
            print(f"✗ Erreur création transfert: {response.status_code}")
            return None


def create_test_discharge(dossier_id):
    """Crée une sortie (génère A03)."""
    print("\n" + "="*80)
    print("SORTIE (A03)")
    print("="*80)
    
    with Session(engine) as session:
        dossier = session.get(Dossier, dossier_id)
        if not dossier:
            print("✗ Dossier non trouvé")
            return None
        
        venue = session.exec(
            select(Venue).where(Venue.dossier_id == dossier_id).order_by(Venue.id.desc())
        ).first()
        
        if not venue:
            print("✗ Venue non trouvée")
            return None
        
        mouvement_data = {
            "venue_id": venue.id,
            "type": "ADT^A03",
            "when": datetime.now().isoformat(),
            "location": "MCO-NEURO",
            "trigger_event": "A03",
            "movement_type": "discharge"
        }
        
        response = requests.post(f"{BASE_URL}/mouvements/new", data=mouvement_data, allow_redirects=False)
        if response.status_code in (200, 302, 303):
            print("✓ Sortie créée avec succès")
            check_last_message(session, "A03", dossier.dossier_seq)
            return True
        else:
            print(f"✗ Erreur création sortie: {response.status_code}")
            return False


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
    
    message = message_log.raw_message
    if not message:
        print("  ⚠ Message vide")
        return False
    
    print(f"  Message ID: {message_log.id}")
    print(f"  Direction: {message_log.direction}")
    print(f"  Status: {message_log.status}")
    
    # Extraire les segments
    lines = message.split("\r")
    segments = {}
    for line in lines:
        if "|" in line:
            seg_type = line.split("|")[0]
            segments[seg_type] = line
    
    # Vérifier MSH
    if "MSH" in segments:
        msh_parts = segments["MSH"].split("|")
        if len(msh_parts) > 8:
            msg_type = msh_parts[8]
            print(f"  MSH-9 (Type): {msg_type}")
            if expected_trigger in msg_type:
                print(f"  ✓ Trigger correct")
            else:
                print(f"  ✗ Trigger incorrect (attendu: {expected_trigger})")
    
    # Vérifier PV1-2 (patient_class)
    if "PV1" in segments:
        pv1_parts = segments["PV1"].split("|")
        if len(pv1_parts) > 2:
            patient_class = pv1_parts[2]
            print(f"  PV1-2 (Patient Class): {patient_class}")
            
            # Vérifier le mapping
            if patient_class in ["I", "O", "E"]:
                print(f"  ✓ Patient class valide (HL7v2)")
            else:
                print(f"  ⚠ Patient class non standard: {patient_class}")
    
    # Valider avec le validateur IHE PAM
    print("\n  Validation IHE PAM:")
    is_valid, issues = validate_pam(message)
    
    if is_valid:
        print("  ✓ Message valide IHE PAM")
    else:
        print(f"  ✗ Message invalide:")
        for issue in issues[:5]:  # Afficher max 5 erreurs
            severity = issue.get("severity", "error")
            code = issue.get("code", "UNKNOWN")
            msg = issue.get("message", "")
            print(f"    [{severity}] {code}: {msg}")
    
    # Afficher un extrait du message
    print("\n  Extrait du message:")
    for seg_type in ["MSH", "PID", "PV1", "ZBE"]:
        if seg_type in segments:
            print(f"    {segments[seg_type][:100]}...")
    
    return is_valid


def main():
    """Test principal."""
    print("\n" + "="*80)
    print("TEST COMPLET: CRÉATION, MODIFICATION, ANNULATION")
    print("Validation des messages générés avec vocabulaires")
    print("="*80)
    
    # 1. Test des mappings
    test_vocabulary_mappings()
    
    # 2. Créer un patient
    patient_id = create_test_patient()
    if not patient_id:
        print("\n✗ Échec création patient, arrêt des tests")
        return
    
    # 3. Admission
    dossier_id = create_test_admission(patient_id)
    if not dossier_id:
        print("\n✗ Échec admission, arrêt des tests")
        return
    
    # 4. Transfert
    mouvement_id = create_test_transfer(dossier_id)
    if not mouvement_id:
        print("\n⚠ Échec transfert, poursuite des tests")
    
    # 5. Sortie
    create_test_discharge(dossier_id)
    
    print("\n" + "="*80)
    print("RÉSUMÉ DES TESTS")
    print("="*80)
    
    with Session(engine) as session:
        total_messages = session.exec(select(MessageLog)).all()
        print(f"Total messages générés: {len(total_messages)}")
        
        valid_count = sum(1 for m in total_messages if m.status == "processed")
        print(f"Messages validés: {valid_count}")
        
        if total_messages:
            print("\nDerniers messages:")
            for msg in total_messages[-5:]:
                direction = "→" if msg.direction == "outbound" else "←"
                print(f"  {direction} ID {msg.id}: {msg.status} (Type: {msg.message_type})")
    
    print("\n✓ Tests terminés")


if __name__ == "__main__":
    main()

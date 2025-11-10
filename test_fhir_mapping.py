#!/usr/bin/env python3
"""
Test du nouveau mapping FHIR avec architecture correcte :
- Patient → Patient
- Dossier → EpisodeOfCare
- Venue → Encounter
- Mouvement → Encounter (nested)
"""

import sys
import json
from sqlmodel import Session, select
from app.db import engine
from app.models import Patient, Dossier, Venue, Mouvement, DossierType
from app.services.fhir_resources import (
    generate_patient_resource,
    generate_episode_of_care_resource,
    generate_encounter_resource_for_venue,
    generate_encounter_resource_for_mouvement,
    generate_fhir_bundle_for_entity
)
from datetime import datetime, date
from app.utils.seq_generator import generate_patient_seq, generate_dossier_seq
from app.db import get_next_sequence

def test_fhir_mapping():
    print("\n" + "="*100)
    print("🧪 TEST MAPPING FHIR - ARCHITECTURE CORRECTE")
    print("="*100 + "\n")
    
    with Session(engine) as session:
        # 1. Créer un patient
        print("📝 Étape 1/5 : Création patient...")
        patient_seq = generate_patient_seq()
        patient = Patient(
            family="TestFHIR",
            given="Marie",
            birth_date=date(1990, 5, 15),
            gender="F",
            patient_seq=patient_seq,
            identifier=str(patient_seq),
            email="marie.test@example.com"
        )
        session.add(patient)
        session.commit()
        session.refresh(patient)
        print(f"   ✅ Patient ID={patient.id}, patient_seq={patient.patient_seq}")
        
        # Test Patient resource
        patient_res = generate_patient_resource(patient)
        print(f"   ✅ Patient FHIR: resourceType={patient_res['resourceType']}, id={patient_res['id']}")
        assert patient_res["resourceType"] == "Patient"
        assert "identifier" in patient_res
        print()
        
        # 2. Créer un dossier
        print("📝 Étape 2/5 : Création dossier (IMP)...")
        dossier_seq = generate_dossier_seq()
        dossier = Dossier(
            patient_id=patient.id,
            uf_responsabilite="CARDIO",
            dossier_type=DossierType.HOSPITALISE,
            admit_time=datetime.now(),
            dossier_seq=dossier_seq,
            encounter_class="IMP"
        )
        session.add(dossier)
        session.commit()
        session.refresh(dossier)
        session.refresh(dossier, ["patient"])
        print(f"   ✅ Dossier ID={dossier.id}, dossier_seq={dossier.dossier_seq}")
        
        # Test EpisodeOfCare resource
        episode_res = generate_episode_of_care_resource(dossier, session)
        print(f"   ✅ EpisodeOfCare FHIR: resourceType={episode_res['resourceType']}, id={episode_res['id']}")
        print(f"      Status: {episode_res['status']}")
        print(f"      Patient ref: {episode_res['patient']['reference']}")
        assert episode_res["resourceType"] == "EpisodeOfCare"
        assert episode_res["status"] in ["planned", "active", "finished"]
        assert "IMP" in str(episode_res.get("type", []))
        print()
        
        # 3. Créer une venue
        print("📝 Étape 3/5 : Création venue...")
        import random
        venue_seq = random.randint(900000000, 999999999)
        venue = Venue(
            dossier_id=dossier.id,
            uf_responsabilite="CARDIO",
            start_time=datetime.now(),
            venue_seq=venue_seq,
            code="ADMIT",
            label="Admission cardiologie",
            attending_provider="Dr. Durand"
        )
        session.add(venue)
        session.commit()
        session.refresh(venue)
        session.refresh(venue, ["dossier"])
        session.refresh(venue.dossier, ["patient"])
        print(f"   ✅ Venue ID={venue.id}, venue_seq={venue.venue_seq}")
        
        # Test Encounter resource for venue
        encounter_venue_res = generate_encounter_resource_for_venue(venue, session)
        print(f"   ✅ Encounter (venue) FHIR: resourceType={encounter_venue_res['resourceType']}, id={encounter_venue_res['id']}")
        print(f"      Status: {encounter_venue_res['status']}")
        print(f"      Class: {encounter_venue_res['class']['code']}")
        print(f"      EpisodeOfCare ref: {encounter_venue_res['episodeOfCare'][0]['reference']}")
        assert encounter_venue_res["resourceType"] == "Encounter"
        assert encounter_venue_res["class"]["code"] == "IMP"
        assert "EpisodeOfCare/eoc-" in encounter_venue_res["episodeOfCare"][0]["reference"]
        print()
        
        # 4. Créer un mouvement
        print("📝 Étape 4/5 : Création mouvement A01...")
        from app.utils.seq_generator import generate_dossier_seq as gen_mvt_seq
        mvt_seq = gen_mvt_seq()  # Utiliser même générateur pour test
        mouvement = Mouvement(
            venue_id=venue.id,
            mouvement_seq=mvt_seq,
            type="ADT^A01",
            when=datetime.now(),
            location="CARDIO-101"
        )
        session.add(mouvement)
        session.commit()
        session.refresh(mouvement)
        session.refresh(mouvement, ["venue"])
        session.refresh(mouvement.venue, ["dossier"])
        session.refresh(mouvement.venue.dossier, ["patient"])
        print(f"   ✅ Mouvement ID={mouvement.id}, type={mouvement.type}")
        
        # Test Encounter resource for mouvement
        encounter_mvt_res = generate_encounter_resource_for_mouvement(mouvement, session)
        print(f"   ✅ Encounter (mouvement) FHIR: resourceType={encounter_mvt_res['resourceType']}, id={encounter_mvt_res['id']}")
        print(f"      Status: {encounter_mvt_res['status']}")
        print(f"      Type: {encounter_mvt_res['type'][0]['coding'][0]['code']}")
        print(f"      PartOf ref: {encounter_mvt_res['partOf']['reference']}")
        assert encounter_mvt_res["resourceType"] == "Encounter"
        assert encounter_mvt_res["status"] == "arrived"
        assert "A01" in encounter_mvt_res["type"][0]["coding"][0]["code"]
        assert "Encounter/enc-venue-" in encounter_mvt_res["partOf"]["reference"]
        print()
        
        # 5. Test bundles complets
        print("📝 Étape 5/5 : Génération bundles complets...")
        
        # Bundle patient
        bundle_patient = generate_fhir_bundle_for_entity(patient, "patient", session)
        print(f"   ✅ Bundle Patient: {len(bundle_patient['entry'])} ressources")
        assert bundle_patient["resourceType"] == "Bundle"
        assert len(bundle_patient["entry"]) == 1
        assert bundle_patient["entry"][0]["resource"]["resourceType"] == "Patient"
        
        # Bundle dossier
        bundle_dossier = generate_fhir_bundle_for_entity(dossier, "dossier", session)
        print(f"   ✅ Bundle Dossier: {len(bundle_dossier['entry'])} ressources")
        assert len(bundle_dossier["entry"]) == 2  # EpisodeOfCare + Patient
        resource_types = [e["resource"]["resourceType"] for e in bundle_dossier["entry"]]
        assert "EpisodeOfCare" in resource_types
        assert "Patient" in resource_types
        
        # Bundle venue
        bundle_venue = generate_fhir_bundle_for_entity(venue, "venue", session)
        print(f"   ✅ Bundle Venue: {len(bundle_venue['entry'])} ressources")
        assert len(bundle_venue["entry"]) == 3  # Encounter + EpisodeOfCare + Patient
        resource_types = [e["resource"]["resourceType"] for e in bundle_venue["entry"]]
        assert "Encounter" in resource_types
        assert "EpisodeOfCare" in resource_types
        assert "Patient" in resource_types
        
        # Bundle mouvement
        bundle_mvt = generate_fhir_bundle_for_entity(mouvement, "mouvement", session)
        print(f"   ✅ Bundle Mouvement: {len(bundle_mvt['entry'])} ressources")
        assert len(bundle_mvt["entry"]) == 4  # Encounter mvt + Encounter venue + EpisodeOfCare + Patient
        resource_types = [e["resource"]["resourceType"] for e in bundle_mvt["entry"]]
        assert resource_types.count("Encounter") == 2  # Mouvement + Venue
        assert "EpisodeOfCare" in resource_types
        assert "Patient" in resource_types
        print()
        
        # 6. Vérifier la structure nested
        print("📝 Vérification architecture nested...")
        mvt_encounter = bundle_mvt["entry"][0]["resource"]
        assert "partOf" in mvt_encounter
        print(f"   ✅ Mouvement Encounter.partOf: {mvt_encounter['partOf']['reference']}")
        
        venue_encounter = bundle_mvt["entry"][1]["resource"]
        assert "episodeOfCare" in venue_encounter
        print(f"   ✅ Venue Encounter.episodeOfCare: {venue_encounter['episodeOfCare'][0]['reference']}")
        print()
        
        # 7. Afficher un exemple de bundle complet
        print("="*100)
        print("📦 EXEMPLE DE BUNDLE MOUVEMENT (structure complète)")
        print("="*100)
        print(json.dumps(bundle_mvt, indent=2))
        print()
        
        print("="*100)
        print("✅ TOUS LES TESTS FHIR SONT PASSÉS !")
        print("="*100 + "\n")
        
        print("📊 Résumé de l'architecture FHIR :")
        print(f"   Patient → Patient resource")
        print(f"   Dossier → EpisodeOfCare resource ✅")
        print(f"   Venue → Encounter resource ✅")
        print(f"   Mouvement → Encounter resource (nested) ✅")
        print(f"   Mouvement.partOf → Venue Encounter ✅")
        print(f"   Venue Encounter.episodeOfCare → Dossier EpisodeOfCare ✅")
        print()
        
        return True

if __name__ == "__main__":
    try:
        success = test_fhir_mapping()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERREUR : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

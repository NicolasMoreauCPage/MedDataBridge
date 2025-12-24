#!/usr/bin/env python3
"""
Test de l'import FHIR avec extraction du médecin responsable.

Ce script crée un Encounter FHIR avec un Practitioner en contained
et vérifie que le médecin est correctement extrait et associé.
"""
import json
from datetime import datetime
from sqlmodel import Session, select
from app.db import session_factory
from app.models import Patient, Dossier, Mouvement
from app.models_structure import EntiteJuridique
from app.models_practitioners import MedecinResponsable
from app.converters.fhir_import_converter import FHIRToEncounterConverter


def create_test_encounter():
    """Crée un Encounter FHIR de test avec Practitioner."""
    return {
        "resourceType": "Encounter",
        "id": "enc-test-001",
        "status": "in-progress",
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "IMP",
            "display": "inpatient encounter"
        },
        "subject": {
            "reference": "Patient/1"  # Patient avec id=1
        },
        "participant": [
            {
                "type": [
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/v3-ParticipationType",
                                "code": "ATND",
                                "display": "attender"
                            }
                        ]
                    }
                ],
                "individual": {
                    "reference": "#pract-1",
                    "display": "Dr DURAND Jean-Pierre"
                }
            }
        ],
        "period": {
            "start": "2024-01-15T10:00:00+01:00"
        },
        "contained": [
            {
                "resourceType": "Practitioner",
                "id": "pract-1",
                "identifier": [
                    {
                        "system": "http://rpps.fr",
                        "value": "12345678901"  # RPPS 11 chiffres
                    }
                ],
                "name": [
                    {
                        "family": "DURAND",
                        "given": ["Jean-Pierre"],
                        "prefix": ["Dr"]
                    }
                ],
                "qualification": [
                    {
                        "code": {
                            "coding": [
                                {
                                    "system": "http://snomed.info/sct",
                                    "code": "394814009",
                                    "display": "Cardiologie"
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }


def main():
    print("=== Test import FHIR avec médecin responsable ===\n")
    
    session = session_factory()
    
    # Vérifier qu'on a un patient avec id=1
    patient = session.get(Patient, 1)
    if not patient:
        print("❌ Aucun patient avec id=1 trouvé dans la base")
        print("   Créez d'abord un patient ou modifiez le script")
        session.close()
        return
    
    print(f"✓ Patient trouvé: {patient.nom} {patient.prenom} (id={patient.id})")
    
    # Vérifier qu'on a un dossier pour ce patient
    dossier = session.exec(select(Dossier).where(Dossier.patient_id == patient.id)).first()
    if not dossier:
        print("❌ Aucun dossier trouvé pour ce patient")
        print("   Créez d'abord un dossier ou modifiez le script")
        session.close()
        return
    
    print(f"✓ Dossier trouvé: id={dossier.id}, dossier_seq={dossier.dossier_seq}")
    
    # Compter les médecins avant
    medecins_avant = session.exec(select(MedecinResponsable)).all()
    print(f"\n📊 Médecins dans la base avant import: {len(medecins_avant)}")
    for med in medecins_avant:
        print(f"   - {med.get_full_name()} ({med.get_identifier()})")
    
    # Créer l'encounter de test
    encounter = create_test_encounter()
    
    print("\n📥 Import de l'Encounter FHIR:")
    print(json.dumps(encounter, indent=2, ensure_ascii=False))
    
    # Importer l'encounter
    converter = FHIRToEncounterConverter(session)
    
    try:
        mouvement = converter.convert_encounter(encounter)
        print(f"\n✅ Encounter importé avec succès!")
        print(f"   Mouvement créé: id={mouvement.id}, type={mouvement.type}")
        
        # Vérifier le médecin
        if mouvement.medecin_responsable_id:
            medecin = session.get(MedecinResponsable, mouvement.medecin_responsable_id)
            if medecin:
                print(f"\n✅ Médecin responsable assigné au mouvement:")
                print(f"   - Nom: {medecin.get_full_name()}")
                print(f"   - Identifiant: {medecin.get_identifier()}")
                print(f"   - RPPS: {medecin.rpps}")
                print(f"   - ADELI: {medecin.adeli}")
                print(f"   - Spécialité: {medecin.specialty}")
            else:
                print(f"⚠️  Médecin id={mouvement.medecin_responsable_id} non trouvé")
        else:
            print("⚠️  Aucun médecin assigné au mouvement")
        
        # Vérifier si le dossier a aussi été mis à jour
        session.refresh(dossier)
        if dossier.medecin_responsable_id:
            print(f"\n✅ Médecin également assigné au dossier (id={dossier.medecin_responsable_id})")
        else:
            print("\nℹ️  Dossier n'a pas été mis à jour (déjà un médecin ou erreur)")
        
        # Compter les médecins après
        medecins_apres = session.exec(select(MedecinResponsable)).all()
        print(f"\n📊 Médecins dans la base après import: {len(medecins_apres)}")
        for med in medecins_apres:
            print(f"   - {med.get_full_name()} ({med.get_identifier()})")
        
        if len(medecins_apres) > len(medecins_avant):
            print(f"\n✅ {len(medecins_apres) - len(medecins_avant)} nouveau(x) médecin(s) créé(s)")
        
    except Exception as e:
        print(f"\n❌ Erreur lors de l'import: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    main()

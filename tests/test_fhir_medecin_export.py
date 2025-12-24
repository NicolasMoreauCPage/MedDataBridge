#!/usr/bin/env python3
"""
Test de l'export FHIR avec médecin responsable.

Vérifie que les ressources Encounter exportées incluent le Practitioner.
"""
import json
from sqlmodel import select
from app.db import session_factory
from app.models import Mouvement
from app.models_practitioners import MedecinResponsable  # Import pour résoudre les relations
from app.services.fhir_encounters import generate_encounter_resource_for_mouvement


def main():
    print("=== Test export FHIR avec médecin responsable ===\n")
    
    session = session_factory()
    
    # Récupérer le dernier mouvement créé (celui du test d'import)
    mouvement = session.exec(
        select(Mouvement).order_by(Mouvement.id.desc())
    ).first()
    
    if not mouvement:
        print("❌ Aucun mouvement trouvé dans la base")
        session.close()
        return
    
    print(f"✓ Mouvement trouvé: id={mouvement.id}, type={mouvement.type}")
    print(f"  Médecin responsable ID: {mouvement.medecin_responsable_id}")
    
    # Générer la ressource FHIR Encounter
    try:
        encounter = generate_encounter_resource_for_mouvement(mouvement, session)
        
        print("\n📤 Ressource Encounter générée:")
        print(json.dumps(encounter, indent=2, ensure_ascii=False))
        
        # Vérifier la présence du participant
        if "participant" in encounter:
            print("\n✅ Participant trouvé dans l'Encounter")
            participant = encounter["participant"][0]
            
            # Vérifier le type ATND
            type_coding = participant.get("type", [{}])[0].get("coding", [{}])[0]
            if type_coding.get("code") == "ATND":
                print("✅ Type de participant: ATND (attender)")
            
            # Vérifier la référence
            individual = participant.get("individual", {})
            reference = individual.get("reference", "")
            display = individual.get("display", "")
            
            print(f"✅ Référence: {reference}")
            print(f"✅ Display: {display}")
            
            # Vérifier la présence du Practitioner contained
            if "contained" in encounter:
                contained = encounter["contained"]
                practitioner = next(
                    (r for r in contained if r.get("resourceType") == "Practitioner"),
                    None
                )
                
                if practitioner:
                    print("\n✅ Practitioner trouvé dans contained:")
                    print(f"   - ID: {practitioner.get('id')}")
                    
                    # Identifiants
                    identifiers = practitioner.get("identifier", [])
                    for ident in identifiers:
                        system = ident.get("system", "")
                        value = ident.get("value", "")
                        if "rpps" in system.lower():
                            print(f"   - RPPS: {value}")
                        elif "adeli" in system.lower():
                            print(f"   - ADELI: {value}")
                    
                    # Nom
                    names = practitioner.get("name", [])
                    if names:
                        name = names[0]
                        family = name.get("family", "")
                        given = " ".join(name.get("given", []))
                        prefix = " ".join(name.get("prefix", []))
                        print(f"   - Nom: {prefix} {family} {given}".strip())
                    
                    # Qualification
                    qualifications = practitioner.get("qualification", [])
                    if qualifications:
                        qual = qualifications[0]
                        specialty = qual.get("code", {}).get("coding", [{}])[0].get("display", "")
                        if specialty:
                            print(f"   - Spécialité: {specialty}")
                else:
                    print("⚠️  Practitioner non trouvé dans contained")
            else:
                print("⚠️  Aucune ressource contained dans l'Encounter")
        else:
            print("⚠️  Aucun participant dans l'Encounter")
        
        print("\n✅ Export FHIR avec médecin responsable fonctionnel!")
        
    except Exception as e:
        print(f"\n❌ Erreur lors de l'export: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    main()

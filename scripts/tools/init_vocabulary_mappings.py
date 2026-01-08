#!/usr/bin/env python3
"""Initialize vocabulary mappings for FHIR structure export/import.

Ce script crée les mappings bidirectionnels entre les codes internes et FHIR pour :
- location-physical-type : Codes physiques (area, wi, ro, bd, etc.)
- location-service-type : Types de service (mco, ssr, psy, etc.)

Les mappings permettent la traduction automatique via map_code() et reverse_map_code().
"""
from sqlmodel import Session, select
from app.db import engine
from app.models_vocabulary import VocabularySystem, VocabularyValue, VocabularyMapping


def init_physical_type_mappings(session: Session):
    """Crée les mappings pour location-physical-type.
    
    Pour l'instant, les codes internes et FHIR sont identiques (mapping 1:1).
    Ceci permet la cohérence avec les messages HL7 MFN qui utilisent les mêmes codes.
    """
    print("\n=== Initialisation des mappings location-physical-type ===")
    
    # Récupérer le système source
    source_system = session.exec(
        select(VocabularySystem).where(VocabularySystem.name == "location-physical-type")
    ).first()
    
    if not source_system:
        print("❌ Système 'location-physical-type' non trouvé")
        return
    
    print(f"✅ Système source trouvé : {source_system.label} (id={source_system.id})")
    
    # Pour l'instant, mapping 1:1 vers le même système
    # (futur : pourrait mapper vers un système FHIR distinct)
    target_system = source_system
    
    # Codes à mapper
    codes = ["si", "bu", "wi", "fl", "ro", "bd", "ve", "ho", "ca", "rd", "area", "jdn"]
    
    mappings_created = 0
    mappings_skipped = 0
    
    for code in codes:
        # Trouver la valeur source
        source_value = session.exec(
            select(VocabularyValue)
            .where(VocabularyValue.system_id == source_system.id)
            .where(VocabularyValue.code == code)
        ).first()
        
        if not source_value:
            print(f"  ⚠️  Code '{code}' non trouvé dans le système source")
            continue
        
        # Vérifier si le mapping existe déjà
        existing = session.exec(
            select(VocabularyMapping)
            .where(VocabularyMapping.source_value_id == source_value.id)
            .where(VocabularyMapping.target_system_id == target_system.id)
            .where(VocabularyMapping.target_code == code)
        ).first()
        
        if existing:
            mappings_skipped += 1
            continue
        
        # Créer le mapping
        mapping = VocabularyMapping(
            source_value_id=source_value.id,
            target_system_id=target_system.id,
            target_code=code,
            map_type="equivalent"
        )
        session.add(mapping)
        mappings_created += 1
        print(f"  ✅ Mapping créé : {code} → {code}")
    
    session.commit()
    print(f"\n📊 Résultat : {mappings_created} créés, {mappings_skipped} déjà existants")


def init_service_type_mappings(session: Session):
    """Crée les mappings pour location-service-type.
    
    Mapping 1:1 entre codes internes et FHIR (identiques pour l'instant).
    """
    print("\n=== Initialisation des mappings location-service-type ===")
    
    # Récupérer le système source
    source_system = session.exec(
        select(VocabularySystem).where(VocabularySystem.name == "location-service-type")
    ).first()
    
    if not source_system:
        print("❌ Système 'location-service-type' non trouvé")
        return
    
    print(f"✅ Système source trouvé : {source_system.label} (id={source_system.id})")
    
    # Pour l'instant, mapping 1:1 vers le même système
    target_system = source_system
    
    # Codes à mapper
    codes = ["mco", "ssr", "psy", "had", "ehpad", "usld"]
    
    mappings_created = 0
    mappings_skipped = 0
    
    for code in codes:
        # Trouver la valeur source
        source_value = session.exec(
            select(VocabularyValue)
            .where(VocabularyValue.system_id == source_system.id)
            .where(VocabularyValue.code == code)
        ).first()
        
        if not source_value:
            print(f"  ⚠️  Code '{code}' non trouvé dans le système source")
            continue
        
        # Vérifier si le mapping existe déjà
        existing = session.exec(
            select(VocabularyMapping)
            .where(VocabularyMapping.source_value_id == source_value.id)
            .where(VocabularyMapping.target_system_id == target_system.id)
            .where(VocabularyMapping.target_code == code)
        ).first()
        
        if existing:
            mappings_skipped += 1
            continue
        
        # Créer le mapping
        mapping = VocabularyMapping(
            source_value_id=source_value.id,
            target_system_id=target_system.id,
            target_code=code,
            map_type="equivalent"
        )
        session.add(mapping)
        mappings_created += 1
        print(f"  ✅ Mapping créé : {code} → {code}")
    
    session.commit()
    print(f"\n📊 Résultat : {mappings_created} créés, {mappings_skipped} déjà existants")


def main():
    """Point d'entrée principal."""
    print("=" * 70)
    print("Initialisation des mappings de vocabulaire pour FHIR structure")
    print("=" * 70)
    
    with Session(engine) as session:
        init_physical_type_mappings(session)
        init_service_type_mappings(session)
    
    print("\n" + "=" * 70)
    print("✅ Initialisation terminée avec succès !")
    print("=" * 70)
    print("\n💡 Les fonctions map_code() et reverse_map_code() peuvent maintenant")
    print("   traduire les codes pour l'export/import FHIR de structures.")


if __name__ == "__main__":
    main()
